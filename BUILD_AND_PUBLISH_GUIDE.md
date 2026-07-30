# CONCLAVE - Build, Test, and Publish Guide

This guide is for **package maintainers** who want to build and publish CONCLAVE to PyPI.

---

## 📋 Prerequisites

### 1. Required Accounts
- **PyPI account**: Register at https://pypi.org/account/register/
- **TestPyPI account** (optional but recommended): https://test.pypi.org/account/register/

### 2. API Tokens
Create API tokens for uploading:

**PyPI:**
1. Log in to https://pypi.org
2. Go to Account Settings → API tokens
3. Click "Add API token"
4. Scope: "Entire account" (first time) or "Project: conclave" (after first upload)
5. Save the token (starts with `pypi-`)

**TestPyPI:**
1. Log in to https://test.pypi.org
2. Repeat same steps

### 3. Configure API Tokens

Create `~/.pypirc`:
```bash
cat > ~/.pypirc << 'EOF'
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR_PYPI_TOKEN_HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR_TESTPYPI_TOKEN_HERE
EOF

chmod 600 ~/.pypirc
```

### 4. Install Build Tools

```bash
pip install build twine
```

---

## 🏗️ Building the Package

### Step 1: Verify Package Structure

```bash
cd conclave/
ls -la

# Should see:
# ├── pyproject.toml  ← Main config
# ├── README.md
# ├── LICENSE
# ├── conclave/       ← Source code
# └── ...
```

### Step 2: Clean Previous Builds

```bash
# Remove old build artifacts
rm -rf build/ dist/ *.egg-info/
```

### Step 3: Build Package

```bash
python -m build
```

**Output:**
```
Successfully built conclave-1.0.0.tar.gz and conclave-1.0.0-py3-none-any.whl
```

**Creates:**
```
dist/
├── conclave-1.0.0.tar.gz           # Source distribution
└── conclave-1.0.0-py3-none-any.whl # Wheel (recommended format)
```

---

## 🧪 Testing the Package Locally

### Test 1: Install from Wheel

```bash
# Create clean test environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install package
pip install dist/conclave-1.0.0-py3-none-any.whl

# Test imports
python << 'EOF'
import conclave
print(f"✅ Version: {conclave.__version__}")

from conclave import run_annotation_pipeline, run_phase2_complete
print("✅ Main functions imported")

from conclave.phase1 import normalize_markers
print("✅ Phase 1 imported")

from conclave.phase2.pipeline_complete import run_phase2_complete
print("✅ Phase 2 imported")

print("\n✅ ALL TESTS PASSED!")
EOF
```

### Test 2: Check Dependencies Auto-Install

```bash
# Create clean environment
python -m venv test_deps
source test_deps/bin/activate

# Install package (should auto-install dependencies)
pip install dist/conclave-1.0.0-py3-none-any.whl

# Check if dependencies are installed
pip list | grep -E "numpy|pandas|scikit-learn|matplotlib"

# Should show installed versions
```

### Test 3: Run Quick Functional Test

```bash
python << 'EOF'
import pandas as pd
import numpy as np
from conclave.phase1 import normalize_markers

# Create test data
df = pd.DataFrame({
    'CD3': np.random.randn(1000),
    'CD4': np.random.randn(1000),
    'CD8': np.random.randn(1000),
})

# Test normalization
df_norm, report = normalize_markers(df, ['CD3', 'CD4', 'CD8'], method='z-score')

print(f"✅ Normalized {len(df_norm)} cells")
print(f"✅ Method: {report['method']}")
print("✅ Package is working!")
EOF
```

### Test 4: Check Package Metadata

```bash
# Inspect package
pip show conclave

# Should show:
# Name: conclave
# Version: 1.0.0
# Summary: Consensus-based Labeling...
# Requires: numpy, pandas, scipy, ...
```

---

## 🚀 Publishing to PyPI

### Option A: Publish to TestPyPI First (Recommended)

Test the upload process without affecting the real PyPI:

```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ conclave

# Note: --extra-index-url allows installing dependencies from real PyPI
```

**View your package:** https://test.pypi.org/project/conclave/

### Option B: Publish to PyPI (Production)

Once you've tested on TestPyPI:

```bash
# Upload to PyPI
twine upload dist/*
```

**What happens:**
1. Twine uploads both `.tar.gz` and `.whl` files
2. PyPI processes and publishes your package
3. Package is immediately available: `pip install conclave`

**View your package:** https://pypi.org/project/conclave/

---

## ✅ Verification After Publishing

### Test Installation from PyPI

```bash
# Create clean environment
python -m venv verify_env
source verify_env/bin/activate

# Install from PyPI
pip install conclave

# Verify
python -c "import conclave; print(conclave.__version__)"

# Should print: 1.0.0
```

### Check PyPI Page

Visit https://pypi.org/project/conclave/ and verify:
- ✅ README displays correctly
- ✅ Version is correct (1.0.0)
- ✅ Dependencies are listed
- ✅ Download links work

---

## 🔄 Updating the Package

When you need to release a new version:

### Step 1: Update Version

Edit `pyproject.toml`:
```toml
[project]
version = "1.0.1"  # or 1.1.0, 2.0.0, etc.
```

### Step 2: Update CHANGELOG.md

Document changes in `CHANGELOG.md`:
```markdown
## [1.0.1] - 2026-03-15

### Fixed
- Bug fix description

### Added
- New feature description
```

### Step 3: Rebuild and Republish

```bash
# Clean old builds
rm -rf dist/ build/ *.egg-info/

# Build new version
python -m build

# Upload to PyPI
twine upload dist/*
```

---

## 🐛 Troubleshooting

### Error: "File already exists"

**Problem:** You're trying to upload a version that already exists

**Solution:** PyPI doesn't allow replacing files. You must:
1. Increment version in `pyproject.toml`
2. Rebuild: `python -m build`
3. Upload new version: `twine upload dist/*`

### Error: "Invalid credentials"

**Problem:** API token is wrong or expired

**Solution:**
1. Generate new token on PyPI
2. Update `~/.pypirc` with new token
3. Try upload again

### Error: "HTTPError: 400 Bad Request"

**Problem:** Package metadata is invalid

**Solution:**
```bash
# Check package before uploading
twine check dist/*

# Should output: PASSED
```

### Warning: "long_description_content_type not specified"

**Problem:** README format not specified

**Solution:** Verify `pyproject.toml` has:
```toml
[project]
readme = "README.md"
```

---

## 📝 Pre-Release Checklist

Before publishing to PyPI, verify:

- [ ] Version bumped in `pyproject.toml`
- [ ] CHANGELOG.md updated
- [ ] All tests pass locally
- [ ] README.md is up-to-date
- [ ] Dependencies are correct in `pyproject.toml`
- [ ] `python -m build` succeeds
- [ ] `twine check dist/*` passes
- [ ] Tested installation locally
- [ ] Tested on TestPyPI (optional)
- [ ] Git tagged with version: `git tag v1.0.0`

---

## 🎯 Quick Reference

```bash
# Build package
python -m build

# Check package
twine check dist/*

# Upload to TestPyPI (test first)
twine upload --repository testpypi dist/*

# Upload to PyPI (production)
twine upload dist/*

# Test installation
pip install conclave
```

---

## 📞 Support

- **PyPI Help**: https://pypi.org/help/
- **Twine Docs**: https://twine.readthedocs.io/
- **Packaging Guide**: https://packaging.python.org/

---

## 🎉 Success!

Once published, users can install with:
```bash
pip install conclave
```

Your package is now part of the Python ecosystem! 🎊
