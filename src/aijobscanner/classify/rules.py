"""
Classification rules for AI Job Scanner.

Defines keyword groups with weights for heuristic classification of job posts.
English-only support (EN).
"""

from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
import re


@dataclass
class ClassificationResult:
    """Result of classifying a message."""
    is_ai_relevant: int
    score: float
    reasons: List[str]
    metadata: Dict[str, Any]


# Keyword groups with weights
KEYWORD_GROUPS = {
    "tech_core_high": {
        "weight": 1.0,
        "keywords_en": [
            # Core programming
            "software", "developer", "programmer", "engineer", "coding", "coder",
            "full stack", "full-stack", "backend", "back-end", "front-end", "frontend",
            "web app", "webapp", "web development", "website",
            "api", "API", "microservice", "micro-service", "soa", "service oriented",
            "database", "db", "sql", "SQL", "postgresql", "postgres", "psql",
            "mongodb", "mysql", "oracle", "database admin", "dba", "data engineer",
            "software engineer", "application developer", "app developer",
            "web developer", "webdev", "mobile developer", "ios", "android",
            # Frameworks & Languages
            "react", "angular", "vue", "django", "flask", "spring", "spring boot",
            ".net", "dotnet", "java", "c++", "c#", "c sharp", "python", "ruby", "php",
            "laravel", "symfony", "express", "nodejs", "node.js", "javascript", "typescript",
            "go", "golang", "rust", "swift", "kotlin", "scala",
            # Backend specific
            "server-side", "serverside", "backend dev", "backend development",
            "rest", "restful", "rest api", "graphql", "grpc", "soap",
            "web service", "web services", "client-server", "mvc", "mvp",
            # Database specific
            "sql developer", "database developer", "data modelling", "data modeling",
            "nosql", "newsql", "document database", "relational database",
            "query optimization", "database design", "data architecture",
            # Architecture
            "architecture", "software architecture", "system design", "technical design",
            "design patterns", "solid", "clean code", "agile", "scrum", "kanban",
        ],
    },
    "automation_high": {
        "weight": 1.0,
        "keywords_en": [
            # Core automation
            "automation", "automate", "automated", "automating",
            "script", "scripting", "scripts", "scripting language",
            # Programming languages for automation
            "python", "PYTHON",
            "node", "nodejs", "node.js",
            "javascript", "js", "typescript",
            "bash", "shell", "shell scripting", "shell script",
            "powershell", "windows scripting",
            # Scheduling & workflows
            "cron", "scheduler", "scheduling", "scheduled task",
            "etl", "extract transform load", "data pipeline",
            "workflow", "work-flow", "pipeline", "pipelining",
            "orchestration", "orchestrator", "airflow", "dag", "directed acyclic graph",
            # Bots & automation
            "bot", "chatbot", "telegram bot", "discord bot",
            "webhook", "webhooks", "api integration", "integration", "integrations",
            "rpa", "robotic process automation", "macros", "macro",
            # Automation engineering
            "automation engineer", "automation specialist",
            "scripting language", "interpreted language", "dynamic language",
            # CI/CD & DevOps overlap
            "continuous integration", "ci", "continuous delivery", "cd",
            "build automation", "deployment automation", "release automation",
            # Data automation
            "data processing", "data pipeline", "batch processing",
            "stream processing", "event-driven", "event driven",
        ],
    },
    "devops_high": {
        "weight": 1.0,
        "keywords_en": [
            # DevOps core
            "devops", "site reliability engineer", "sre",
            "ci/cd", "cicd", "ci cd", "continuous integration", "continuous deployment",
            "continuous delivery", "infrastructure as code", "iaac",
            # Container & Orchestration
            "docker", "container", "containers", "containerization",
            "kubernetes", "k8s", "kubernetes cluster", "k8s cluster",
            "container orchestration", "pod", "deployment", "deploying",
            "helm", "chart", "kompose", "docker compose",
            # Cloud Providers
            "aws", "amazon web services", "ec2", "s3", "lambda",
            "gcp", "google cloud", "gke", "google kubernetes engine",
            "azure", "microsoft azure", "aks", "azure kubernetes service",
            "cloud computing", "cloud native", "serverless", "function as a service", "faas",
            # Infrastructure as Code
            "terraform", "ansible", "chef", "puppet", "saltstack",
            "cloudformation", "arm template",
            # Operating Systems
            "linux", "unix", "unix-like", "posix",
            "windows server", "windows admin", "system admin",
            "red hat", "rhel", "centos", "ubuntu", "debian",
            # Servers & Infrastructure
            "server", "servers", "infrastructure", "infra",
            "deployment", "deploy", "release engineering",
            "version control", "git", "gitlab", "github", "bitbucket", "vcs",
            "configuration management", "configuration", "config management",
            # Monitoring & Logging
            "monitoring", "logging", "observability", "metrics", "alerting",
            "prometheus", "grafana", "elk", "elk stack", "splunk",
            # Networking
            "network", "networking", "cdn", "content delivery network",
            "load balancer", "reverse proxy", "nginx", "apache",
            # Scaling
            "scaling", "scalability", "horizontal scaling", "vertical scaling",
            "high availability", "ha", "disaster recovery", "dr",
        ],
    },
    "ai_ml_high": {
        "weight": 1.0,
        "keywords_en": [
            # AI/ML Core
            "ai", "artificial intelligence", "machine intelligence",
            "ml", "machine learning", "statistical learning",
            "llm", "large language model", "language model",
            # LLMs & Generative AI
            "gpt", "chatgpt", "gpt-4", "claude", "gemini", "bard",
            "openai", "anthropic", "google ai", "hugging face",
            "prompt", "prompting", "prompt engineering", "prompt design",
            "in-context learning", "few-shot", "zero-shot", "fine-tuning",
            "training", "inference", "model deployment",
            # NLP
            "nlp", "natural language processing", "text analytics",
            "text mining", "sentiment analysis", "text classification",
            "named entity recognition", "ner", "part of speech tagging", "pos tagging",
            "tokenization", "embedding", "word embeddings", "vector embeddings",
            "transformer", "transformers", "attention mechanism", "self-attention",
            "bert", "roberta", "t5", "llama", "mistral", "phi",
            # Computer Vision
            "computer vision", "cv", "image processing", "image recognition",
            "object detection", "object recognition", "image classification",
            "segmentation", "semantic segmentation", "instance segmentation",
            "face recognition", "ocr", "optical character recognition",
            "video analysis", "video processing",
            # Agents & Robotics
            "agent", "agents", "ai agent", "autonomous agent",
            "multi-agent system", "multiagent", "swarm intelligence",
            "reinforcement learning", "rl", "deep rl", "q-learning",
            # Data Science
            "data science", "data scientist", "data analytics", "data analysis",
            "big data", "data engineering", "data pipeline", "etl",
            "pandas", "numpy", "scipy", "scikit-learn", "sklearn", "matplotlib",
            "jupyter", "notebook", "colab", "kaggle",
            # Deep Learning Frameworks
            "tensorflow", "tf", "keras", "pytorch", "torch",
            "caffe", "mxnet", "theano", "CNTK",
            # Neural Networks
            "neural network", "neural net", "deep learning", "dl", "deepnet",
            "cnn", "rnn", "lstm", "gru", "gan", "generative", "discriminative",
            "backpropagation", "gradient descent", "optimization",
            # Applications
            "recommendation system", "recommender", "personalization",
            "search engine", "information retrieval", "ranking",
            "chatbot", "conversational ai", "virtual assistant", "voice assistant",
            "speech recognition", "speech to text", "text to speech", "tts",
            "generative ai", "genai", "text generation", "image generation",
            "foundation model", "pretrained", "transfer learning",
        ],
    },
    "security_high": {
        "weight": 1.0,
        "keywords_en": [
            # Security Core
            "security", "cybersecurity", "cyber security", "infosec",
            "pentest", "penetration testing", "pen testing", "pen-test",
            "ethical hacking", "white hat", "white-hat", "security research",
            # Security Operations
            "soc", "security operations center", "security analyst",
            "siem", "security information", "event management",
            "soc analyst", "tier 1", "tier 2", "tier 3 security",
            # Vulnerability Management
            "vulnerability", "vulnerabilities", "vulnerability assessment",
            "vulnerability scanning", "vuln scan", "security assessment",
            "penetration testing", "pentesting", "security audit",
            # OWASP & Standards
            "owasp", "owasp top 10", "security standard",
            "iso 27001", "pci dss", "gdpr", "hipaa", "compliance",
            # Threats & Attacks
            "malware", "malware analysis", "ransomware", "virus",
            "phishing", "social engineering", "threat intelligence", "threat hunting",
            "incident response", "ir", "incident handling", "forensics",
            # Security Engineering
            "secure coding", "security review", "code review", "security testing",
            "application security", "appsec", "web security", "network security",
            "endpoint security", "mobile security", "cloud security",
            # Specific Vulnerabilities
            "injection", "sql injection", "xss", "csrf", "cross-site scripting",
            "authentication", "authorization", "zero trust", "encryption",
            "cryptography", "cryptographic", "firewall", "ids", "ips",
            "intrusion detection", "intrusion prevention", "dlp", "data loss prevention",
            # Security Tools
            "metasploit", "burp suite", "nmap", "wireshark", "snort",
            "splunk", "qradar", "arcsight", "qualys", "rapid7",
        ],
    },
    "it_support_mid": {
        "weight": 0.7,
        "keywords_en": [
            # IT Support Core
            "it support", "it support specialist", "technical support",
            "helpdesk", "help desk", "service desk", "support analyst",
            "sysadmin", "system administrator", "linux admin", "windows admin",
            # System Administration
            "system administration", "systems administration", "systems admin",
            "server administration", "server admin", "infrastructure administration",
            # Network & Connectivity
            "network", "networking", "network engineer", "network administrator",
            "network support", "network operations", "netops", "noc",
            "dns", "domain", "domain name system", "bind",
            "vpn", "virtual private network", "remote access",
            "ip addressing", "subnetting", "routing", "switch", "router",
            # Directory Services
            "active directory", "ad", "ldap", "domain controller", "dc",
            "identity management", "idm", "iam", "access management",
            "user management", "account management", "provisioning", "deprovisioning",
            # Desktop Support
            "desktop support", "endpoint management", "device management",
            "desktop administration", "windows desktop", "macos", "linux desktop",
            "endpoint", "endpoints", "workstation", "laptop", "mobile device",
            # IT Operations
            "it operations", "it ops", "operations", "maintenance", "break-fix",
            "troubleshooting", "issue resolution", "technical support", "tier 1", "tier 2",
            # System Monitoring
            "system monitoring", "performance monitoring", "log analysis",
            "alerting", "on-call", "incident management", "ticketing",
            # Windows Specific
            "windows server", "windows administration", "microsoft", "exchange",
            "office 365", "o365", "intune", "sccm", "system center",
            # Linux Specific
            "linux administration", "linux engineering", "rhel", "centos", "ubuntu",
            "shell scripting", "bash scripting", "linux commands",
            # Virtualization
            "vmware", "virtualization", "hypervisor", "virtual machine", "vm",
            "hyper-v", "virtualbox", "kvm", "xen",
        ],
    },
    "remote_low": {
        "weight": 0.2,
        "keywords_en": [
            # Remote Work Core
            "remote", "remote work", "remote job", "remote position",
            "wfh", "work from home", "work-from-home",
            "telecommute", "telecommuting", "telework", "teleworking",
            "virtual", "virtual office", "distributed team",
            "location independent", "location-independent",
            # Employment Types
            "freelance", "freelancer", "freelancing", "contract",
            "contractor", "contracting", "contract-to-hire", "contract position",
            "project-based", "project based", "project work",
            "consultant", "consulting", "independent", "self-employed",
            "temporary", "temp", "contract position",
            # Flexible Work
            "flexible", "flexible schedule", "flexitime",
            "hybrid", "hybrid work", "remote-first",
            "digital nomad", "nomad", "location independent",
            "asynchronous", "async", "async communication",
            "global", "worldwide", "distributed team",
            # Specific Terms
            "remote-friendly", "remote ok", "remote possible",
            "work from anywhere", "wfa", "home-based",
        ],
    },
    "negative_nontech": {
        "weight": -1.0,
        "keywords_en": [
            # Retail & Food Service
            "cashier", "cashiering", "cash register", "store clerk",
            "waiter", "waitress", "bartender", "barista",
            "barback", "sommelier", "host", "hostess",
            "food service", "restaurant", "fast food", "food runner",
            "delivery driver", "food delivery", "uber eats", "doordash", "grubhub",
            "restaurant server", "food server", "serving tables", "table server",
            # Manual Labor
            "driver", "truck driver", "delivery driver", "chauffeur",
            "warehouse", "warehousing", "picker", "packer", "stock clerk",
            "construction", "laborer", "builder", "tradesperson",
            "carpenter", "electrician", "plumber", "welder", "painter",
            # Maintenance & Cleaning
            "cleaner", "cleaning", "custodian", "janitor", "caretaker",
            "maintenance", "repair", "technician", "mechanic", "auto repair",
            "landscaping", "gardener", "groundkeeper", "lawn care",
            # Security (non-IT)
            "security guard", "guard", "bouncer", "doorman", "loss prevention",
            "store detective", "loss prevention officer",
            # Customer Service (non-technical)
            "receptionist", "front desk", "customer service representative", "csr",
            "call center", "call center agent", "telemarketer", "telemarketing",
            "customer support", "support agent", "phone support",
            # Education (non-technical)
            "teacher", "teaching", "tutor", "education", "instructor",
            "professor", "lecturer", "academic", "faculty",
            "teacher aide", "teaching assistant",
            # Healthcare (non-technical)
            "nurse", "doctor", "physician", "medical", "healthcare",
            "caregiver", "home health aide", "medical assistant",
            # Sales (non-technical)
            "retail", "sales associate", "salesperson", "sales representative",
            "account manager", "business development", "sales executive",
            "insurance agent", "real estate agent",
            # Office Support (non-technical)
            "data entry", "data entry clerk", "typist", "filing",
            "administrative assistant", "admin assistant", "office clerk",
            "receptionist", "office admin",
            # Hospitality
            "hotel", "hospitality", "hotel staff", "concierge",
            # Transportation (non-technical)
            "taxi", "cab driver", "delivery person", "courier",
            "manufacturing", "factory", "assembly line", "production worker",
            "quality control", "qc", "inspector", "production",
            # Other Manual Labor
            "loader", "unloader", "mover", "warehouse worker",
            "stocking", "inventory", "stock clerk",
            "general labor", "manual labor", "physical labor",
        ],
    },
}


def classify(text: str) -> ClassificationResult:
    """
    Classify a message text for AI/automation relevance.

    Uses weighted keyword matching with guardrails:
    - Remote keywords only count if tech keywords matched
    - Negative keywords filter out non-tech jobs

    Args:
        text: Message text to classify

    Returns:
        ClassificationResult with is_ai_relevant (0/1), score, reasons, metadata
    """
    if not text:
        return ClassificationResult(
            is_ai_relevant=0,
            score=0.0,
            reasons=[],
            metadata={"matched_keywords": [], "matched_groups": [], "guardrail_triggered": False}
        )

    text_lower = text.lower()

    # Track matches
    matched_keywords = []
    matched_groups = []
    weights_applied = []
    negative_matches = []
    score_breakdown = {}

    # Check each keyword group
    for group_name, group_data in KEYWORD_GROUPS.items():
        group_weight = group_data["weight"]
        group_keywords = [k.lower() for k in group_data["keywords_en"]]

        group_matches = []
        group_score = 0.0

        # Check keywords using word boundary matching
        for keyword in group_keywords:
            # Use word boundary regex to avoid substring matches
            # Escape special regex characters in keyword
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text_lower, re.IGNORECASE):
                group_matches.append(keyword)
                group_score += group_weight

        if group_matches:
            if group_name == "negative_nontech":
                negative_matches.extend(group_matches)
            else:
                matched_keywords.extend(group_matches)
                matched_groups.append(group_name)
                weights_applied.append(group_weight)
                score_breakdown[group_name] = group_score

    # Calculate base score
    base_score = sum(weights_applied)

    # Guardrail: remote keywords require tech keywords
    remote_keywords_matched = any(g in matched_groups for g in ["remote_low"])
    tech_keywords_matched = any(g in matched_groups for g in [
        "tech_core_high", "automation_high", "devops_high",
        "ai_ml_high", "security_high", "it_support_mid"
    ])

    if remote_keywords_matched and not tech_keywords_matched:
        # Remote without tech = not relevant
        base_score = 0.0
        guardrail_triggered = True
    else:
        guardrail_triggered = False

    # Negative keyword filter with multi-word phrase check
    if negative_matches:
        # Check if any negative multi-word phrases contain tech keywords
        # For example, "restaurant server" contains "server" (tech keyword)
        # In this case, the negative context should override
        negative_phrases = [m for m in negative_matches if len(m.split()) > 1]

        if negative_phrases:
            # If we have negative multi-word phrases, check if tech keywords
            # appear within them. If so, this is likely a negative context.
            for phrase in negative_phrases:
                for tech_keyword in matched_keywords:
                    if tech_keyword in phrase.lower():
                        # Tech keyword appears in negative phrase (e.g., "server" in "restaurant server")
                        # This is a negative context, so treat as not relevant
                        if not tech_keywords_matched or len(matched_keywords) <= 1:
                            base_score = 0.0
                            guardrail_triggered = True
                            break
                if guardrail_triggered:
                    break

        # Original negative filter: negative without tech = not relevant
        if not guardrail_triggered and not tech_keywords_matched:
            base_score = 0.0
            guardrail_triggered = True

    # Determine if AI-relevant (score threshold: 0.7)
    is_ai_relevant = 1 if base_score >= 0.7 else 0

    # Generate reasons
    reasons = []
    if "tech_core_high" in matched_groups:
        reasons.append("Software/IT development")
    if "automation_high" in matched_groups:
        reasons.append("Automation/scripting")
    if "devops_high" in matched_groups:
        reasons.append("DevOps/cloud")
    if "ai_ml_high" in matched_groups:
        reasons.append("AI/ML")
    if "security_high" in matched_groups:
        reasons.append("Security")
    if "it_support_mid" in matched_groups:
        reasons.append("IT support")
    if "remote_low" in matched_groups and tech_keywords_matched:
        reasons.append("Remote work")

    # Build metadata
    metadata = {
        "matched_keywords": matched_keywords,
        "matched_groups": matched_groups,
        "weights_applied": weights_applied,
        "negative_matches": negative_matches,
        "score_breakdown": score_breakdown,
        "guardrail_triggered": guardrail_triggered,
    }

    return ClassificationResult(
        is_ai_relevant=is_ai_relevant,
        score=round(base_score, 2),
        reasons=reasons,
        metadata=metadata,
    )


def get_keyword_groups() -> Dict[str, Dict[str, Any]]:
    """
    Get all keyword groups for reference/tuning.

    Returns:
        Dict mapping group names to group data
    """
    return KEYWORD_GROUPS.copy()


def add_keyword(group_name: str, keyword: str) -> bool:
    """
    Add a keyword to a group (for runtime tuning).

    Args:
        group_name: Name of keyword group
        keyword: Keyword to add

    Returns:
        True if added, False if group not found
    """
    if group_name not in KEYWORD_GROUPS:
        return False

    KEYWORD_GROUPS[group_name]["keywords_en"].append(keyword)
    return True
