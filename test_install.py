#!/usr/bin/env python3
"""
CONCLAVE Installation Test Script
Run this after installing to verify everything works.
"""

import sys

def test_imports():
    """Test all imports"""
    print("="*80)
    print("Testing CONCLAVE Installation")
    print("="*80)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Basic import
    print("\n[1/5] Testing basic import...")
    try:
        import conclave
        print(f"    ✅ Version: {conclave.__version__}")
        tests_passed += 1
    except Exception as e:
        print(f"    ❌ Failed: {e}")
        tests_failed += 1
        return False
    
    # Test 2: Main functions
    print("\n[2/5] Testing main functions...")
    try:
        from conclave import run_annotation_pipeline, run_phase2_complete
        print("    ✅ Main functions imported")
        tests_passed += 1
    except Exception as e:
        print(f"    ❌ Failed: {e}")
        tests_failed += 1
    
    # Test 3: Phase 1 modules
    print("\n[3/5] Testing Phase 1 modules...")
    try:
        from conclave.phase1 import (
            normalize_markers,
            sample_umap_tiles,
            cluster_annotation_subset,
        )
        print("    ✅ Phase 1 modules imported")
        tests_passed += 1
    except Exception as e:
        print(f"    ❌ Failed: {e}")
        tests_failed += 1
    
    # Test 4: Phase 2 modules
    print("\n[4/5] Testing Phase 2 modules...")
    try:
        from conclave.phase2.pipeline_complete import run_phase2_complete
        from conclave.phase2 import consensus, projection, flagging
        print("    ✅ Phase 2 modules imported")
        tests_passed += 1
    except Exception as e:
        print(f"    ❌ Failed: {e}")
        tests_failed += 1
    
    # Test 5: Dependencies
    print("\n[5/5] Testing dependencies...")
    try:
        import numpy
        import pandas
        import scipy
        import sklearn
        import matplotlib
        import seaborn
        import umap
        print(f"    ✅ Core dependencies:")
        print(f"       - numpy: {numpy.__version__}")
        print(f"       - pandas: {pandas.__version__}")
        print(f"       - scikit-learn: {sklearn.__version__}")
        tests_passed += 1
    except Exception as e:
        print(f"    ❌ Failed: {e}")
        tests_failed += 1
    
    # Test 6: GPU (optional)
    print("\n[OPTIONAL] Testing GPU support...")
    try:
        import cuml
        import cupy as cp
        print(f"    ✅ GPU support available:")
        print(f"       - cuML: {cuml.__version__}")
        print(f"       - GPU: {cp.cuda.Device(0).name.decode()}")
    except ImportError:
        print("    ℹ️  GPU support not installed (this is OK for CPU-only use)")
    except Exception as e:
        print(f"    ⚠️  GPU support installed but error: {e}")
    
    # Summary
    print("\n" + "="*80)
    print(f"Tests passed: {tests_passed}/{tests_passed + tests_failed}")
    
    if tests_failed == 0:
        print("✅ Installation verified successfully!")
        print("\nYou can now use CONCLAVE:")
        print("  from conclave import run_annotation_pipeline")
        return True
    else:
        print("❌ Some tests failed. Please check installation.")
        return False


def test_functionality():
    """Test basic functionality"""
    print("\n" + "="*80)
    print("Testing Basic Functionality")
    print("="*80)
    
    try:
        import pandas as pd
        import numpy as np
        from conclave.phase1 import normalize_markers
        
        print("\nCreating test dataset...")
        df = pd.DataFrame({
            'CD3': np.random.randn(1000),
            'CD4': np.random.randn(1000),
            'CD8': np.random.randn(1000),
        })
        
        print("Running normalization...")
        df_norm, report = normalize_markers(
            df, 
            ['CD3', 'CD4', 'CD8'], 
            method='z-score'
        )
        
        print(f"\n✅ Functional test passed!")
        print(f"   - Normalized {len(df_norm)} cells")
        print(f"   - Method: {report['method']}")
        print(f"   - Output shape: {df_norm.shape}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Functional test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    imports_ok = test_imports()
    
    if imports_ok:
        functionality_ok = test_functionality()
        
        if functionality_ok:
            print("\n" + "="*80)
            print("🎉 All tests passed! CONCLAVE is ready to use!")
            print("="*80)
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        sys.exit(1)
