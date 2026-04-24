"""GPU detection for Whisper acceleration."""
import os


def detect_device():
    """Returns (device, compute_type, description) for faster-whisper."""
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            cap = torch.cuda.get_device_capability(0)
            vram = torch.cuda.get_device_properties(0).total_mem // (1024**2)
            if cap[0] >= 7:
                return "cuda", "float16", f"GPU: {name} ({vram}MB VRAM) - FAST MODE"
            else:
                return "cpu", "int8", f"GPU: {name} (too old, CUDA {cap[0]}.{cap[1]}) - Using CPU"
    except ImportError:
        pass
    cores = os.cpu_count() or 4
    return "cpu", "int8", f"CPU: {cores} threads (int8 optimized)"
