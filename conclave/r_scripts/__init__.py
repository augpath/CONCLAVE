"""Reference R scripts for FlowSOM and DepecheR clustering.

These are NOT Python modules -- this __init__.py exists only so setuptools
treats r_scripts/ as a package and bundles the .R files into the wheel.
Access the scripts via importlib.resources or by locating this package's
directory, e.g.:

    import conclave.r_scripts
    from pathlib import Path
    script_dir = Path(conclave.r_scripts.__file__).parent
    flowsom_script = script_dir / "flowsom_clustering.R"
"""
