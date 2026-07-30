# CONCLAVE - Master Guide

Complete guide for building, publishing, and distributing the CONCLAVE Python package.

---

## 📦 Package Structure

```
conclave/
├── pyproject.toml              ⭐ PRIMARY - Package configuration
├── README.md                   ⭐ Shows on PyPI
├── LICENSE                     ⭐ MIT License
├── MANIFEST.in                 Files to include in distribution
│
├── requirements.txt            For developers/CI/CD
├── requirements-dev.txt        Development dependencies
├── environment.yml             Conda + GPU support
├── environment-cpu.yml         Conda CPU-only
│
├── BUILD_AND_PUBLISH_GUIDE.md  ⭐ For maintainers
├── USER_INSTALLATION_GUIDE.md  ⭐ For end users
├── test_install.py             Installation test script
│
├── conclave/                   ⭐ Source code (100% complete)
│   ├── __init__.py
│   ├── phase1/                 6 files, 108 KB
│   └── phase2/                 8 files, 70 KB
│
├── examples/                   Usage examples
└── tests/                      Unit tests
```

---

## 🎯 Three Roles, Three Guides

### 1. Package Maintainer (You)
**Goal:** Build and publish to PyPI

**Read:** `BUILD_AND_PUBLISH_GUIDE.md`

**Quick Steps:**
```bash
# Build
python -m build

# Test locally
pip install dist/conclave-1.0.0-py3-none-any.whl

# Publish
twine upload dist/*
```

---

### 2. End User (Most People)
**Goal:** Install and use CONCLAVE

**Read:** `USER_INSTALLATION_GUIDE.md` or `README.md`

**Installation:**
```bash
pip install conclave
```

That's it! Dependencies auto-install.

---

### 3. Developer/Contributor
**Goal:** Modify and improve CONCLAVE

**Installation:**
```bash
git clone https://github.com/augpath/CONCLAVE.git
cd conclave
pip install -e ".[dev]"
```

---

## 📋 What Each File Does

### Core Files (Required)

**`pyproject.toml`** - THE MOST IMPORTANT FILE
- Defines package name, version, dependencies
- Used by pip to install dependencies automatically
- Modern Python standard (PEP 621)
- **This is why dependencies auto-install!**

**`README.md`**
- Shows on PyPI package page
- Installation instructions for users
- Quick start examples

**`LICENSE`**
- MIT License (required for PyPI)
- Allows free use, modification, distribution

**`conclave/`**
- Source code directory
- Phase 1 and Phase 2 complete implementation

---

### Optional Files (But Recommended)

**`requirements.txt`**
- For developers and CI/CD
- NOT needed by end users (pyproject.toml handles this)
- Same content as `dependencies` in pyproject.toml

**`environment.yml`**
- For conda users with GPU
- Installs cuML, CUDA, all dependencies
- Creates complete environment

**`MANIFEST.in`**
- Specifies which files to include in distribution
- Include docs, examples, tests

**`test_install.py`**
- Quick test script for users
- Verifies installation worked

---

## 🔄 How Dependency Management Works

### The Modern Way (pyproject.toml)

When you publish to PyPI with `pyproject.toml`:

```toml
[project]
dependencies = [
    "numpy>=1.22,<2.0",
    "pandas>=1.5,<3.0",
    ...
]
```

**What happens when users run `pip install conclave`:**

1. pip downloads conclave-1.0.0-py3-none-any.whl
2. pip reads dependency list from wheel metadata
3. pip automatically installs numpy, pandas, scipy, etc.
4. User can immediately use conclave

**Users don't need to manually install anything!**

---

### Why Include requirements.txt?

**For developers:**
```bash
# Developer clones repo
git clone https://github.com/augpath/CONCLAVE.git
cd conclave

# Install dependencies
pip install -r requirements.txt

# Install package in editable mode
pip install -e .
```

**For CI/CD:**
```yaml
# .github/workflows/tests.yml
- name: Install dependencies
  run: pip install -r requirements.txt
- name: Install package
  run: pip install .
```

**For Docker:**
```dockerfile
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN pip install .
```

---

### Why Include environment.yml?

**For GPU users:**

GPU packages (cuML) are NOT on PyPI. They're only on conda.

**Workflow:**
```bash
# Step 1: Create conda environment (gets cuML)
conda env create -f environment.yml

# Step 2: Install conclave from PyPI
pip install conclave
```

This separates:
- Conda: GPU packages (cuML, CUDA)
- PyPI: Your package (conclave)

---

## 🚀 Publishing Workflow

### Preparation Checklist

- [ ] Update version in `pyproject.toml`
- [ ] Update `CHANGELOG.md`
- [ ] Verify all tests pass
- [ ] Update README if needed
- [ ] Commit all changes

### Build

```bash
# Clean old builds
rm -rf dist/ build/ *.egg-info/

# Build package
python -m build
```

Creates:
- `dist/conclave-1.0.0.tar.gz` (source)
- `dist/conclave-1.0.0-py3-none-any.whl` (binary)

### Test Locally

```bash
# Create test environment
python -m venv test_env
source test_env/bin/activate

# Install
pip install dist/conclave-1.0.0-py3-none-any.whl

# Test
python test_install.py
```

### Publish to TestPyPI (Optional)

```bash
twine upload --repository testpypi dist/*
```

Test installation:
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ conclave
```

### Publish to PyPI (Production)

```bash
twine upload dist/*
```

**Done!** Package is live at https://pypi.org/project/conclave/

---

## 👥 User Installation Methods

After publishing, users can install in 3 ways:

### Method 1: pip (95% of users)
```bash
pip install conclave
```
Dependencies auto-install!

### Method 2: conda + GPU (5% of users with GPUs)
```bash
conda env create -f environment.yml
conda activate conclave
pip install conclave
```

### Method 3: From source (developers)
```bash
git clone https://github.com/augpath/CONCLAVE.git
cd conclave
pip install -e .
```

---

## 📊 Version Management

Follow **Semantic Versioning** (semver):

- **MAJOR.MINOR.PATCH** (e.g., 1.0.0)
- **MAJOR**: Breaking changes (1.0.0 → 2.0.0)
- **MINOR**: New features (1.0.0 → 1.1.0)
- **PATCH**: Bug fixes (1.0.0 → 1.0.1)

### Releasing Updates

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Git tag: `git tag v1.0.1`
4. Rebuild: `python -m build`
5. Republish: `twine upload dist/*`

---

## 🧪 Testing Strategy

### Before Publishing

```bash
# Run test script
python test_install.py

# Install in clean environment
python -m venv test_env
source test_env/bin/activate
pip install dist/conclave-1.0.0-py3-none-any.whl
python test_install.py
```

### After Publishing

```bash
# Test from PyPI
pip install conclave
python -c "import conclave; print(conclave.__version__)"
```

---

## 🔧 Troubleshooting

### Build Issues

**Error:** `No module named 'build'`
```bash
pip install build
```

**Error:** `pyproject.toml not found`
```bash
# Make sure you're in the package root directory
cd conclave/
ls pyproject.toml  # Should exist
```

### Upload Issues

**Error:** `Invalid credentials`
```bash
# Create PyPI API token and update ~/.pypirc
```

**Error:** `File already exists`
```bash
# Can't replace existing version on PyPI
# Must bump version and rebuild
```

### Installation Issues (Users)

**Error:** `ModuleNotFoundError: No module named 'pandas'`
```bash
# Shouldn't happen! Dependencies should auto-install.
# If it does, reinstall:
pip uninstall conclave -y
pip install conclave
```

---

## 📝 Quick Command Reference

```bash
# Build package
python -m build

# Check package
twine check dist/*

# Test locally
pip install dist/conclave-1.0.0-py3-none-any.whl

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*

# Run tests
python test_install.py
```

---

## 🎓 Key Concepts

### Why pyproject.toml is Enough

Modern Python packaging (PEP 621) uses `pyproject.toml` as the single source of truth:

- ✅ Defines dependencies → Auto-install with pip
- ✅ Defines metadata → Shows on PyPI
- ✅ Defines build system → Creates packages
- ✅ No setup.py needed!

### When to Use setup.py

**You don't need it!** `pyproject.toml` replaced it.

Only needed for:
- Legacy compatibility
- Custom build steps
- C extensions

CONCLAVE doesn't need any of these.

### Why Two Distribution Formats?

When you run `python -m build`, it creates:

1. **`.tar.gz`** (source distribution)
   - Contains source code
   - pip compiles/installs it
   - Slower

2. **`.whl`** (wheel - binary distribution)
   - Pre-built, ready to use
   - pip just extracts it
   - **Faster, preferred**

PyPI accepts both. pip prefers wheels.

---

## 🎯 Summary

**For Maintainers:**
1. Build: `python -m build`
2. Publish: `twine upload dist/*`

**For Users:**
1. Install: `pip install conclave`

**The magic:**
- `pyproject.toml` makes dependencies auto-install
- No manual installation needed
- Just works™

---

## 📚 Additional Resources

- **Python Packaging Guide**: https://packaging.python.org/
- **PyPI Help**: https://pypi.org/help/
- **PEP 621** (pyproject.toml): https://peps.python.org/pep-0621/
- **Semantic Versioning**: https://semver.org/

---

## ✅ Final Checklist

Before first publish:

- [ ] All files in place
- [ ] `pyproject.toml` has correct dependencies
- [ ] README.md is complete
- [ ] Version is 1.0.0
- [ ] `python -m build` works
- [ ] Local install works
- [ ] test_install.py passes
- [ ] PyPI account created
- [ ] API token configured

Then:
```bash
python -m build
twine upload dist/*
```

🎉 **You're live on PyPI!**
