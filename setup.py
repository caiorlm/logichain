"""
Setup script for blockchain package
"""

from setuptools import setup, find_packages

setup(
    name="blockchain",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[],
    python_requires=">=3.6",
    author="LogiChain",
    description="Simple blockchain implementation",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
) 