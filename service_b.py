"""
service_b.py - Servis B: İş Dağıtıcı ve Tüketici (Consumer / Task Runner)
Servis A'dan gelen telemetri verilerine göre sunucu üzerindeki etkileri simüle eder:
- Normal aralıklarda: Düşük gecikme (latency), 0 hata oranı.
- Aykırı değerlerde: Yüksek gecikme, kuyruk şişmesi, hata patlaması ve OOM/çöküş.
"""

import random
from typing import Dict, Any

class WorkloadConsumerService:
    def __init__(self):
        self.queue_size = 10
        self.total_processed = 0
        self.total_failed = 0

    def process_telemetry(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        cpu = telemetry["cpu_usage"]
        ram = telemetry["ram_usage"]
        gpu = telemetry["gpu_usage"]
        temp = telemetry["temperature"]

        # Varsayılan sağlıklı değerler
        latency_ms = round(20.0 + random.uniform(-3, 5), 1)
        error_rate = 0.0
        status = "HEALTHY"
        issue_details = []

        # 1. CPU Throttling Etkisi
        if cpu > 85.0:
            delay_factor = (cpu - 85.0) * 18.0
            latency_ms += delay_factor
            self.queue_size += random.randint(5, 12)
            issue_details.append(f"CPU Throttling aktif (+{round(delay_factor, 1)}ms gecikme)")

        # 2. RAM Doygunluğu ve OOM (Out Of Memory) Etkisi
        if ram > 85.0:
            latency_ms += (ram - 85.0) * 25.0  # Swap/Paging gecikmesi
            if ram > 92.0:
                error_rate += (ram - 90.0) * 8.0  # Bellek yetersizliği hataları
                issue_details.append("Kritik bellek seviyesi: Swap alanı doldu, OOM Killer riski!")

        # 3. GPU ve Termal Darboğaz
        if gpu > 90.0 or temp > 82.0:
            latency_ms += 120.0
            error_rate += 15.0
            issue_details.append("GPU VRAM aşımı veya termal sınırlama (Thermal Throttling)")

        # 4. Genel Durum Belirleme
        if error_rate > 25.0 or ram > 95.0 or cpu > 95.0:
            status = "CRITICAL"
            failed_in_batch = random.randint(4, 15)
            self.total_failed += failed_in_batch
        elif error_rate > 5.0 or latency_ms > 150.0:
            status = "DEGRADED"
        else:
            status = "HEALTHY"
            # Kuyruk yavaşça erir
            self.queue_size = max(5, self.queue_size - random.randint(2, 6))

        # Kuyruk sınırları
        self.queue_size = max(2, min(250, self.queue_size))
        error_rate = min(100.0, round(error_rate, 1))
        latency_ms = round(latency_ms, 1)
        self.total_processed += random.randint(15, 30)

        return {
            "status": status,
            "latency_ms": latency_ms,
            "error_rate_pct": error_rate,
            "queue_depth": self.queue_size,
            "total_processed": self.total_processed,
            "total_failed": self.total_failed,
            "issues": issue_details if issue_details else ["Tüm sistemler stabil"]
        }
