# CONCLAVE - User Installation Guide

Complete installation instructions for CONCLAVE users.

---

## 🎯 Choose Your Installation Method

### For Most Users → [Method 1: pip](#method-1-pip-simple---recommended)
### For GPU Users → [Method 2: conda + GPU](#method-2-conda-with-gpu-support)
### For Developers → [Method 3: From Source](#method-3-from-source-for-developers)

---

## Method 1: pip from GitHub - Recommended

**Best for:** CPU-only users, quick installation

> ⚠️ Not yet on PyPI -- `conclave` is already taken by an unrelated project,
> so this will need a different distribution name before real PyPI
> publication. For now, install directly from GitHub:

### Installation

```bash
pip install git+https://github.com/augpath/CONCLAVE.git
```

That's it! All dependencies are automatically installed.

### Verification

```bash
python -c "import conclave; print(conclave.__version__)"
# Output: 1.0.0
```

### Test It Works

```python
from conclave.phase1 import run_annotation_pipeline_with_resume
print("✅ CONCLAVE is ready to use!")
```

---

## Method 2: conda with GPU Support

**Best for:** Users with NVIDIA GPUs who want 10-100x speedup

### Requirements

- NVIDIA GPU (RTX 2000+, V100, A100, etc.)
- CUDA 11.2+ or 12.x
- 8GB+ GPU memory recommended

### Step 1: Check GPU

```bash
nvidia-smi

# Should show your GPU and CUDA version
```

### Step 2: Download Environment File

Download `environment.yml` from GitHub:
https://github.com/augpath/CONCLAVE/blob/main/environment.yml

### Step 3: Create Conda Environment

```bash
conda env create -f environment.yml
conda activate conclave
```

This installs:
- Python 3.10
- All dependencies
- cuML (GPU acceleration)
- CUDA toolkit

### Step 4: Install CONCLAVE

```bash
pip install git+https://github.com/augpath/CONCLAVE.git
```

### Step 5: Verify GPU Support

```bash
python << 'EOF'
import cuml
import cupy as cp

print("✅ cuML version:", cuml.__version__)
print("✅ GPU:", cp.cuda.Device(0).name.decode())
print("✅ GPU support is working!")
EOF
```

### Using GPU in CONCLAVE

```python
from conclave.phase1 import run_annotation_pipeline_with_resume

# Use GPU acceleration
df_clustered, meta = run_annotation_pipeline_with_resume(
    df=df,
    markers=markers,
    outdir="./output",
    use_gpu=True,  # ← Enable GPU (used for the sampling step's UMAP embedding)
)
```

---

## Method 3: From Source (For Developers)

**Best for:** Developers who want to modify the code

### Step 1: Clone Repository

```bash
git clone https://github.com/augpath/CONCLAVE.git
cd CONCLAVE
```

### Step 2: Install in Editable Mode

```bash
# Basic installation
pip install -e .

# OR with development tools
pip install -e ".[dev]"
```

### Step 3: Verify

```bash
python -c "import conclave; print(conclave.__version__)"
```

### Making Changes

With editable mode (`-e`), any changes you make to the source code are immediately reflected:

```python
# Edit conclave/phase1/utils.py
# Changes are instantly available without reinstalling
```

---

## 🖥️ CPU-Only Installation (Alternative)

If you want to use conda but **without GPU**:

### Download Environment File

Download `environment-cpu.yml` from GitHub

### Create Environment

```bash
conda env create -f environment-cpu.yml
conda activate conclave-cpu
pip install git+https://github.com/augpath/CONCLAVE.git
```

---

## ✅ Post-Installation Checks

Run these commands to verify everything works:

### Check 1: Version

```bash
python -c "import conclave; print(conclave.__version__)"
# Expected: 1.0.0
```

### Check 2: Core Imports

```bash
python << 'EOF'
from conclave import run_annotation_pipeline, run_phase2_complete
from conclave.phase1 import normalize_markers, sample_umap_tiles
from conclave.phase2.pipeline_complete import run_phase2_complete
print("✅ All imports successful!")
EOF
```

### Check 3: Dependencies

```bash
pip list | grep -E "numpy|pandas|scikit-learn"

# Should show installed versions
```

### Check 4: Quick Functional Test

```bash
python << 'EOF'
import pandas as pd
import numpy as np
from conclave.phase1 import normalize_markers

# Create test data
df = pd.DataFrame({
    'CD3': np.random.randn(100),
    'CD4': np.random.randn(100),
})

# Test normalization
df_norm, report = normalize_markers(df, ['CD3', 'CD4'], method='z-score')
print(f"✅ Test passed! Normalized {len(df_norm)} cells")
EOF
```

---

## 🐛 Troubleshooting

### Issue: ModuleNotFoundError: No module named 'pandas'

**This shouldn't happen!** Dependencies should auto-install with the install command above.

**Solution:**
```bash
# Reinstall with explicit dependency installation
pip uninstall conclave -y
pip install git+https://github.com/augpath/CONCLAVE.git --no-cache-dir

# Verify dependencies
pip show conclave | grep Requires
```

### Issue: pip install (from GitHub) fails

**Possible causes:**
1. Old pip version
2. Network issues
3. Python version <3.8

**Solutions:**
```bash
# Update pip
pip install --upgrade pip

# Check Python version
python --version
# Must be 3.8 or higher

# Try again
pip install git+https://github.com/augpath/CONCLAVE.git
```

### Issue: GPU not detected

**Symptoms:**
```python
ImportError: No module named 'cuml'
```

**This is NORMAL if you didn't install GPU support!**

**Solution 1:** Install GPU support
```bash
conda install -c rapidsai cuml=26.02 cuda-version=12.2 -y
```

**Solution 2:** Use CPU mode (no installation needed)
```python
run_annotation_pipeline(..., use_gpu=False)
```

### Issue: cuML installation fails

**Common cause:** CUDA version mismatch

**Solution:**
```bash
# Check your CUDA version
nvidia-smi
# Look for "CUDA Version: X.X"

# Install matching cuML:
# For CUDA 11.x:
conda install cuml=26.02 cuda-version=11.8 -y

# For CUDA 12.x:
conda install cuml=26.02 cuda-version=12.2 -y
```

### Issue: Slow performance

**Tips:**
- Use GPU if available (10-100x faster)
- Reduce `sample_size` parameter
- Use fewer clustering methods
- Close other applications

### Issue: Permission denied

**Symptoms:**
```
ERROR: Could not install packages due to an OSError: [Errno 13] Permission denied
```

**Solution:**
```bash
# Install in user directory
pip install --user git+https://github.com/augpath/CONCLAVE.git

# OR use virtual environment
python -m venv venv
source venv/bin/activate
pip install git+https://github.com/augpath/CONCLAVE.git
```

---

## 💡 Installation Tips

### Use Virtual Environments

Always use virtual environments to avoid conflicts:

```bash
# Create environment
python -m venv conclave_env

# Activate
source conclave_env/bin/activate  # Linux/Mac
# OR
conclave_env\Scripts\activate     # Windows

# Install
pip install git+https://github.com/augpath/CONCLAVE.git
```

### Update CONCLAVE

```bash
pip install --upgrade git+https://github.com/augpath/CONCLAVE.git
```

### Uninstall CONCLAVE

```bash
pip uninstall conclave
```

---

## 📊 System Requirements

### Minimum (CPU mode)
- **OS**: Linux, macOS, Windows (WSL2 recommended)
- **Python**: 3.8+
- **RAM**: 16GB
- **Storage**: 1GB

### Recommended (CPU mode)
- **Python**: 3.10
- **RAM**: 32GB
- **CPU**: 8+ cores

### GPU Mode
- **GPU**: NVIDIA with Compute Capability 7.0+
  - RTX 2000/3000/4000 series
  - V100, A100
  - T4
- **CUDA**: 11.2+ or 12.x
- **GPU RAM**: 8GB+

---

## 🎓 Next Steps

After installation:

1. **Read Quick Start**: See README.md
2. **Try Examples**: Check `examples/` directory
3. **Read Documentation**: https://conclave.readthedocs.io
4. **Join Community**: https://github.com/augpath/CONCLAVE/discussions

---

## 📞 Getting Help

### Installation Issues
- GitHub Issues: https://github.com/augpath/CONCLAVE/issues
- Tag your issue with `installation`

### Include in Bug Reports
```bash
# System info
python --version
pip --version
pip show conclave

# Python packages
pip list | grep -E "conclave|numpy|pandas"

# GPU info (if relevant)
nvidia-smi
python -c "import cuml; print(cuml.__version__)"
```

---

## 🎉 Success!

Once installed, you can start using CONCLAVE:

```python
from conclave.phase1 import run_annotation_pipeline_with_resume

# Your analysis here
df_clustered, meta = run_annotation_pipeline_with_resume(...)
```

Welcome to the CONCLAVE community! 🎊
