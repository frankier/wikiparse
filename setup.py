from setuptools import find_packages, setup

setup(
    name="wikiparse",
    version="0.0.1",
    description="Wiktionary parsing for Finnish word definitions",
    author="Frankie Robertson",
    author_email="frankie@robertson.name",
    packages=find_packages(exclude=("test", "wikiparse")),
    zip_safe=False,
)
