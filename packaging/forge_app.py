"""Entry point of the packed Windows program (PyInstaller)."""
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()          # must run first in a frozen program (worker processes)
    from atlasforge.app import main
    main()
