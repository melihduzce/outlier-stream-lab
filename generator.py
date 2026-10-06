"""
generator.py - Servis A: Bulut Sunucu Telemetri Üreticisi
CPU, RAM, GPU, Sıcaklık ve Aktif Görev verilerini anlık (streaming) olarak üretir.
Normal akış ve kontrollü anomali enjeksiyon modlarını destekler.
"""

import math
import random
import time
from typing import Dict, Any

class TelemetryGenerator:
    def __init__(self):
        self.tick = 0
        self.mode = "NORMAL"  # NORMAL, MEMORY_LEAK, CPU_BURST, GPU_RUNAWAY, CRITICAL_CRASH
        
        # Temel durum değişkenleri
        self.ram_leak_level = 45.0
        self.base_temp = 50.0

    def set_mode(self, mode: str):
        valid_modes = ["NORMAL", "MEMORY_LEAK", "CPU_BURST", "GPU_RUNAWAY", "CRITICAL_CRASH"]
        if mode in valid_modes:
            self.mode = mode
            if mode == "NORMAL":
                self.ram_leak_level = 45.0  # Reset leak
            return True
        return False

    def generate_next(self) -> Dict[str, Any]:
        self.tick += 1
        t = self.tick

        # Normal dalgalanmalar (günlük döngü veya periyodik iş yükü simülasyonu)
        wave = math.sin(t / 10.0) * 10.0
        noise = random.gauss(0, 2.5)

        # 1. Normal Aralıklar
        cpu = 35.0 + wave + noise
        gpu = 25.0 + (math.cos(t / 8.0) * 8.0) + random.gauss(0, 2.0)
        active_tasks = int(20 + wave * 0.5 + random.randint(-3, 3))
        
        # RAM varsayılan seviye
        ram = self.ram_leak_level + (math.sin(t / 15.0) * 3.0) + random.gauss(0, 1.0)
        temp = self.base_temp + (cpu * 0.2) + (gpu * 0.15) + random.gauss(0, 1.0)

        # 2. Anomali Enjeksiyon Senaryoları (Outliers)
        if self.mode == "MEMORY_LEAK":
            # Her adımda bellek kademeli artar ve bırakılmaz (OOM riski)
            self.ram_leak_level = min(98.5, self.ram_leak_level + 2.5)
            ram = self.ram_leak_level + random.gauss(0, 0.5)
            # Yüksek bellek paging/swap başlatır, sıcaklığı ve cpu'yu hafif tetikler
            cpu += 15.0

        elif self.mode == "CPU_BURST":
            # Beklenmedik kripto madencilik veya sonsuz döngü (CPU %95-100)
            cpu = min(100.0, 95.0 + random.uniform(0, 5))
            temp += 25.0
            active_tasks += 40

        elif self.mode == "GPU_RUNAWAY":
            # Yapay zeka modeli bellek sızıntısı veya kilitlenme
            gpu = min(100.0, 96.0 + random.uniform(0, 4))
            temp += 28.0
            cpu += 20.0

        elif self.mode == "CRITICAL_CRASH":
            # Tüm metriklerin tavana vurduğu kriz anı
            self.ram_leak_level = 97.0
            ram = 97.5 + random.uniform(0, 2)
            cpu = 98.0 + random.uniform(0, 2)
            gpu = 95.0 + random.uniform(0, 5)
            temp = 88.0 + random.uniform(0, 4)
            active_tasks += 60

        # Sınırlandırmalar (0 - 100%)
        cpu = max(0.0, min(100.0, round(cpu, 2)))
        ram = max(0.0, min(100.0, round(ram, 2)))
        gpu = max(0.0, min(100.0, round(gpu, 2)))
        temp = max(30.0, min(105.0, round(temp, 1)))
        active_tasks = max(0, active_tasks)

        return {
            "timestamp": time.strftime("%H:%M:%S"),
            "tick": self.tick,
            "mode": self.mode,
            "cpu_usage": cpu,
            "ram_usage": ram,
            "gpu_usage": gpu,
            "temperature": temp,
            "active_tasks": active_tasks
        }
