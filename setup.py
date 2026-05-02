from setuptools import setup, find_packages

setup(
    name="torven",
    version="0.1.0",
    description="TORVEN — a stack-based compiled language with its own VM",
    packages=find_packages(),
    install_requires=["ply>=3.11"],
    entry_points={
        "console_scripts": [
            "torven=torven.main:main",
        ],
    },
    python_requires=">=3.10",
)
