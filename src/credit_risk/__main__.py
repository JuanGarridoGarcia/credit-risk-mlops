"""Default command of the Docker image: print the package version and exit."""

from credit_risk import __version__


def main() -> None:
    """Print the installed version of the package."""
    print(f"credit-risk {__version__}")


if __name__ == "__main__":
    main()
