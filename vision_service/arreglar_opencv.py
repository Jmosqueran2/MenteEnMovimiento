"""Deja instalado solo opencv-python-headless.

ultralytics y mediapipe arrastran opencv-python y opencv-contrib-python; los
tres instalan el mismo módulo cv2 y juntos lo rompen. Ejecutar después de
`pip install -r requirements.txt`.
"""

import subprocess
import sys

pip = [sys.executable, "-m", "pip"]
subprocess.run([*pip, "uninstall", "-y", "-q", "opencv-python", "opencv-contrib-python",
                "opencv-python-headless"], check=False)
subprocess.run([*pip, "install", "-q", "opencv-python-headless==5.0.0.93"], check=True)
print("OpenCV listo:", subprocess.run([sys.executable, "-c", "import cv2; print(cv2.__version__)"],
                                      capture_output=True, text=True).stdout.strip())
