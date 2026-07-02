from setuptools import setup, find_packages

setup(
    name="reysnap",
    version="1.0.0",
    description="A PixPin-like screenshot, annotation, and pin tool for Linux",
    long_description=open("README.md").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="reyartus",
    license="MIT",
    packages=[
        "reysnap",
        "reysnap.capture",
        "reysnap.annotation",
        "reysnap.pin",
        "reysnap.colorpicker",
        "reysnap.ruler",
        "reysnap.preferences",
    ],
    package_data={
        "reysnap": [],
    },
    install_requires=[
        "PySide6>=6.6.0",
        "Pillow>=10.0.0",
        "python-xlib>=0.33",
        "pynput>=1.7.6",
        "pytesseract>=0.3.10",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "reysnap=reysnap.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Graphics :: Capture :: Screen Capture",
        "Topic :: Utilities",
    ],
)