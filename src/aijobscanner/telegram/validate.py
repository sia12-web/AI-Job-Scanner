"""
Telegram source validation logic.

Uses Telethon to validate access to Telegram groups and channels.
"""

import os
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.types import Channel, Chat


class SourceValidator:
    """
    Validates access to Telegram sources (groups and channels).

    Uses MTProto user session to:
    - Join groups via invite links
    - Subscribe to channels via public handles
    - Verify message readability
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        session_dir: str,
        two_fa_password: Optional[str] = None,
    ):
        """
        Initialize the validator.

        Args:
            api_id: Telegram API ID from my.telegram.org
            api_hash: Telegram API hash from my.telegram.org
            phone: Phone number for the monitoring account
            session_dir: Directory to store session files
            two_fa_password: Optional 2FA password for the account
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.two_fa_password = two_fa_password

        # Create session directory if needed
        session_path = Path(session_dir)
        session_path.mkdir(parents=True, exist_ok=True)

        # Session file name (based on phone number, sanitized)
        session_name = phone.replace("+", "").replace(" ", "_")
        session_file = str(session_path / session_name)

        self.client = TelegramClient(
            session_file,
            api_id,
            api_hash,
        )

        self.session_dir = session_dir

    async def connect(self) -> None:
        """
        Connect to Telegram and authenticate.

        On first run, will request SMS code and 2FA password (if enabled).
        On subsequent runs, will use saved session.
        """
        # Check if this is first run (no session file)
        session_file = Path(self.client.session.filename)
        is_first_run = not session_file.exists()

        await self.client.connect()

        if not await self.client.is_user_authorized():
            # First run - need to authenticate
            print(f"\n=== First-Time Authentication ===")
            print(f"Phone: {self.phone}")
            print(f"Sending code request...")

            await self.client.send_code_request(self.phone)

            # Request SMS code from user
            while True:
                try:
                    code = input("\nEnter the SMS code you received: ").strip()
                    if not code:
                        print("Code cannot be empty. Please try again.")
                        continue

                    # Attempt to sign in with the code
                    try:
                        await self.client.sign_in(self.phone, code)
                        break
                    except errors.SessionPasswordNeededError:
                        # 2FA is enabled
                        if not self.two_fa_password:
                            print("\n[WARN] Two-factor authentication is enabled on this account.")
                            print("Please set TG_2FA_PASSWORD in your .env file and try again.")
                            raise

                        print("\n2FA password required. Using password from environment...")
                        await self.client.sign_in(password=self.two_fa_password)
                        break
                    except errors.PhoneCodeInvalidError:
                        print("[ERROR] Invalid code. Please try again.")
                    except Exception as e:
                        print(f"[ERROR] Error during sign in: {e}")
                        raise

                except KeyboardInterrupt:
                    print("\n\nAuthentication cancelled.")
                    raise

            print("[OK] Authentication successful!")
            print(f"Session saved to: {session_file}")
            print("[WARN] KEEP THIS FILE SECRET - treat it like a password")
        else:
            print(f"[OK] Using existing session: {session_file}")

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        await self.client.disconnect()

    def _extract_invite_hash(self, invite_link: str) -> str:
        """
        Extract invite hash from invite link.

        Args:
            invite_link: Full invite link (e.g., https://t.me/+ABC123...)

        Returns:
            Just the hash portion (e.g., ABC123...)
        """
        # Handle various invite link formats
        # https://t.me/+HASH or https://t.me/joinchat/HASH
        if "+/" in invite_link:
            # https://t.me/+HASH/ format (with slash)
            return invite_link.split("+/")[-1]
        elif "t.me/+" in invite_link:
            # https://t.me/+HASH format (no slash after +)
            return invite_link.split("+")[-1]
        elif "joinchat/" in invite_link:
            # https://t.me/joinchat/HASH format
            return invite_link.split("joinchat/")[-1]
        else:
            # Assume it's already a hash
            return invite_link

    async def validate_source(
        self,
        source: Dict[str, Any],
        message_limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Validate access to a single Telegram source.

        Args:
            source: Source dictionary from telegram_sources.yaml
            message_limit: Number of messages to fetch to verify readability

        Returns:
            Result dictionary with validation status and metadata
        """
        source_id = source.get("source_id")
        source_type = source.get("type")
        invite_link = source.get("invite_link")
        public_handle = source.get("public_handle")

        result = {
            "source_id": source_id,
            "display_name": source.get("display_name"),
            "source_type": source_type,
            "validation_status": "join_failed",
            "last_validated_at": datetime.now(timezone.utc).isoformat(),
            "last_error": None,
            "resolved_entity_id": None,
            "resolved_entity_type": None,
            "messages_readable": False,
            "message_count": 0,
        }

        try:
            # Groups: Join via invite link
            if invite_link:
                print(f"\n[GROUP] Validating: {source.get('display_name')} ({source_id})")
                print(f"   Invite link: {invite_link}")

                invite_hash = self._extract_invite_hash(invite_link)
                print(f"   Invite hash: {invite_hash}")

                try:
                    # Attempt to join the group
                    chat = await self.client(ImportChatInviteRequest(invite_hash))

                    result["resolved_entity_id"] = chat.id
                    result["resolved_entity_type"] = "group"
                    result["validation_status"] = "joined"
                    entity = chat

                    print(f"   [OK] Successfully joined group")

                except errors.InviteHashInvalidError:
                    result["last_error"] = "Invalid invite hash"
                    print(f"   [FAIL] Invalid invite hash")
                    return result

                except errors.InviteHashExpiredError:
                    result["last_error"] = "Invite link expired"
                    print(f"   [FAIL] Invite link expired")
                    return result

                except errors.UserAlreadyParticipantError:
                    # Already joined - need to get the chat entity
                    result["validation_status"] = "joined"
                    print(f"   [OK] Already a member - attempting to get chat entity")

                    # Try to get the chat by iterating through dialogs
                    # This is a workaround for groups where we're already members
                    try:
                        async for dialog in self.client.iter_dialogs():
                            if dialog.is_group:
                                # Check if this is the group we're looking for
                                # For now, we'll skip message verification for already-joined groups
                                result["resolved_entity_id"] = dialog.entity.id
                                result["resolved_entity_type"] = "group"
                                entity = dialog.entity
                                print(f"   [OK] Found group in dialogs: {dialog.name}")
                                break
                    except Exception as e:
                        print(f"   [WARN] Could not get group entity: {e}")
                        entity = None

            # Channels: Subscribe via public handle
            elif public_handle:
                print(f"\n[CHANNEL] Validating: {source.get('display_name')} ({source_id})")
                print(f"   Public handle: @{public_handle}")

                try:
                    # Resolve the channel entity
                    entity = await self.client.get_entity(public_handle)
                    result["resolved_entity_id"] = entity.id
                    result["resolved_entity_type"] = "channel"

                    # Check if we need to join
                    if hasattr(entity, "left") and entity.left:
                        # User has left, need to re-join
                        await self.client(JoinChannelRequest(entity))
                        print(f"   [OK] Subscribed to channel")
                    else:
                        print(f"   [OK] Already subscribed")

                    result["validation_status"] = "joined"

                except errors.ChannelPrivateError:
                    result["last_error"] = "Channel is private"
                    print(f"   [FAIL] Channel is private")
                    return result

                except errors.UsernameNotOccupiedError:
                    result["last_error"] = "Username not found"
                    print(f"   [FAIL] Username not found")
                    return result

            else:
                result["last_error"] = "No invite_link or public_handle found"
                print(f"   [FAIL] No valid access method found")
                return result

            # Verify we can read messages
            if entity:
                target_entity = entity
            elif result["resolved_entity_id"]:
                target_entity = await self.client.get_entity(result["resolved_entity_id"])
            else:
                result["last_error"] = "Failed to resolve entity"
                return result

            # Try to fetch messages
            print(f"   [READ] Checking message readability (limit: {message_limit})...")

            try:
                messages = await self.client.get_messages(
                    target_entity,
                    limit=message_limit,
                )

                if messages is not None:
                    message_count = len(messages) if messages else 0
                    result["messages_readable"] = True
                    result["message_count"] = message_count
                    print(f"   [OK] Successfully read {message_count} messages")
                else:
                    result["validation_status"] = "blocked"
                    result["last_error"] = "Cannot fetch messages"
                    print(f"   [FAIL] Cannot fetch messages (blocked)")

            except errors.ChatForbiddenError:
                result["validation_status"] = "blocked"
                result["last_error"] = "Chat forbidden"
                print(f"   [FAIL] Chat forbidden")

            except Exception as e:
                result["validation_status"] = "blocked"
                result["last_error"] = f"Error fetching messages: {str(e)}"
                print(f"   [FAIL] Error fetching messages: {e}")

        except errors.FloodWaitError as e:
            # Rate limited
            wait_time = e.seconds
            result["validation_status"] = "join_failed"
            result["last_error"] = f"Rate limited. Wait {wait_time} seconds"
            print(f"   [RATE LIMIT] Wait {wait_time} seconds before retrying")

        except Exception as e:
            result["last_error"] = f"Unexpected error: {str(e)}"
            print(f"   [ERROR] Unexpected error: {e}")

        return result

    async def validate_all(
        self,
        sources: List[Dict[str, Any]],
        only_id: Optional[str] = None,
        message_limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Validate multiple sources.

        Args:
            sources: List of source dictionaries
            only_id: If set, only validate this specific source_id
            message_limit: Number of messages to fetch to verify readability

        Returns:
            List of validation result dictionaries
        """
        # Filter to specific source if requested
        if only_id:
            sources = [s for s in sources if s.get("source_id") == only_id]
            if not sources:
                print(f"[ERROR] No source found with ID: {only_id}")
                return []

        print(f"\n[INFO] Starting validation of {len(sources)} source(s)")

        results = []

        for idx, source in enumerate(sources, 1):
            print(f"\n{'='*60}")
            print(f"Source {idx}/{len(sources)}")
            print(f"{'='*60}")

            result = await self.validate_source(source, message_limit)
            results.append(result)

            # Add a small delay between validations to avoid rate limits
            if idx < len(sources):
                delay = 2
                print(f"\n[WAIT] Waiting {delay} seconds before next validation...")
                await asyncio.sleep(delay)

        return results

    def write_report(
        self,
        results: List[Dict[str, Any]],
        report_dir: str,
    ) -> str:
        """
        Write validation results to JSON report file.

        Args:
            results: List of validation result dictionaries
            report_dir: Directory to write report to

        Returns:
            Path to the created report file
        """
        report_path = Path(report_dir)
        report_path.mkdir(parents=True, exist_ok=True)

        # Generate timestamped filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"source_validation_{timestamp}.json"
        filepath = report_path / filename

        # Calculate summary statistics
        total = len(results)
        joined = sum(1 for r in results if r["validation_status"] == "joined")
        failed = sum(1 for r in results if r["validation_status"] == "join_failed")
        blocked = sum(1 for r in results if r["validation_status"] == "blocked")

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_sources": total,
                "joined": joined,
                "failed": failed,
                "blocked": blocked,
            },
            "results": results,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return str(filepath)
