def main() -> None:
    """Run the database seed without pre-importing the executable module.

    Keeping this import lazy is important for ``python -m app.seed.seed_database``:
    Python must execute that module itself rather than find it already loaded by
    package initialization.
    """
    from app.seed.seed_database import main as seed_main

    seed_main()


__all__ = ["main"]
