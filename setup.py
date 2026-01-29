from setuptools import setup, find_packages

setup(
    name="aijobscanner",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "telethon>=1.34.0",
        "pyyaml>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "aijobscanner=aijobscanner.cli:main",
        ],
    },
)
