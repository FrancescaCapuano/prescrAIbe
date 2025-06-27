import subprocess
import torch


def diagnose_cuda():
    """Diagnose CUDA setup and return device information."""
    print("🔍 CUDA Diagnostics:")

    # Check nvidia-smi
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ nvidia-smi works - GPU hardware detected")
        else:
            print("❌ nvidia-smi failed")
    except FileNotFoundError:
        print("❌ nvidia-smi not found")
    except Exception as e:
        print(f"❌ nvidia-smi error: {e}")

    # Check PyTorch CUDA
    cuda_available = torch.cuda.is_available()
    device_count = torch.cuda.device_count()

    print(f"PyTorch CUDA available: {cuda_available}")
    print(f"PyTorch CUDA device count: {device_count}")

    if cuda_available and device_count > 0:
        try:
            device_name = torch.cuda.get_device_name(0)
            print(f"CUDA device name: {device_name}")
            device = "cuda"
        except Exception as e:
            print(f"⚠️  CUDA device name error: {e}")
            device = "cpu"
    else:
        print("Using CPU for embeddings")
        device = "cpu"

    return device
