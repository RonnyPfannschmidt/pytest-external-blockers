from setuptools import setup, find_packages

if __name__ == "__main__":
    setup(
        name="pytest-external-blockers",
        description=(
            "a special outcome for tests "
            "that are blocked for external reasons"),
        use_scm_version=True,
        packages=find_packages("src"),
        package_dir={'': 'src'},
        setup_requires=["setuptools-scm"],
        install_requires=["pytest"],
        entry_points={
            'pytest11': [
                'external-blockers = pytest_external_blockers'
            ],
        }
    )
