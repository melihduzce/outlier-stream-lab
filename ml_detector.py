"""
ml_detector.py - ML Erken Uyarı & Anomali Tespit Servisi
1. Sentetik normal veriler üzerinde Isolation Forest modelini eğitir.
2. Streaming akışından gelen her metriği anlık skorlar (0.0 - 1.0 risk skoru).
3. Aykırı değerleri tespit eder ve kök nedene göre proaktif tedbir bildirimleri üretir.
"""

import numpy as np
from sklearn.ensemble import IsolationForest
from typing import Dict, Any, Tuple, List

class AnomalyDetectorService:
    def __init__(self):
        self.model: IsolationForest = None
        self.feature_names = ["cpu_usage", "ram_usage", "gpu_usage", "temperature", "active_tasks"]
        self.baseline_stats: Dict[str, Dict[str, float]] = {}
        self.is_trained = False
        
        # Başlangıçta sentetik eğitim verisi üretip modeli hazırla
        self.train_baseline()

    def generate_baseline_training_data(self, samples: int = 1200) -> np.ndarray:
        """
        Modelin 'normal' çalışma durumunu öğrenmesi için 
        sentetik temiz telemetri verisi üretir.
        """
        np.random.seed(42)
        
        # Normal CPU: ortalama 38, standart sapma 6 (20 - 55 aralığı)
        cpu = np.clip(np.random.normal(38.0, 6.0, samples), 15.0, 60.0)
        
        # Normal RAM: ortalama 48, standart sapma 4 (35 - 65 aralığı)
        ram = np.clip(np.random.normal(48.0, 4.0, samples), 30.0, 65.0)
        
        # Normal GPU: ortalama 26, standart sapma 5 (10 - 45 aralığı)
        gpu = np.clip(np.random.normal(26.0, 5.0, samples), 5.0, 50.0)
        
        # Normal Sıcaklık: CPU ve GPU ile korele + gürültü (45 - 65 C)
        temp = 48.0 + (cpu * 0.18) + (gpu * 0.12) + np.random.normal(0, 1.5, samples)
        temp = np.clip(temp, 40.0, 70.0)
        
        # Normal Aktif Görev Sayısı
        tasks = np.clip(np.random.poisson(20, samples), 8, 35)

        X = np.column_stack([cpu, ram, gpu, temp, tasks])
        return X

    def train_baseline(self, samples: int = 1200):
        """Isolation Forest algoritmasını sentetik normal veride eğitir."""
        X_train = self.generate_baseline_training_data(samples)

        # Baseline istatistiklerini (ortalama ve standart sapma) sakla
        for i, name in enumerate(self.feature_names):
            mean_val = float(np.mean(X_train[:, i]))
            std_val = float(np.max([np.std(X_train[:, i]), 1e-4]))
            self.baseline_stats[name] = {"mean": mean_val, "std": std_val}

        # Isolation Forest:
        # contamination: eğitim verisindeki olası aykırı değer payı (%3)
        self.model = IsolationForest(
            n_estimators=100,
            contamination=0.03,
            random_state=42,
            n_jobs=-1
        )
        self.model.fit(X_train)
        self.is_trained = True
        return {"status": "trained", "samples": samples, "features": self.feature_names}

    def _calculate_feature_deviations(self, telemetry: Dict[str, Any]) -> List[Tuple[str, float]]:
        """Hangi metriğin normalden en çok saptığını (Z-Score) hesaplar."""
        deviations = []
        for name in self.feature_names:
            val = float(telemetry.get(name, 0.0))
            stats = self.baseline_stats.get(name, {"mean": 0.0, "std": 1.0})
            z_score = (val - stats["mean"]) / stats["std"]
            deviations.append((name, round(z_score, 2)))
        
        # Sapmaya göre en yüksekten en düşüğe sırala
        deviations.sort(key=lambda x: abs(x[1]), reverse=True)
        return deviations

    def analyze_stream(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """Gelen anlık telemetri verisini analiz eder, anomali ve erken uyarı üretir."""
        if not self.is_trained:
            self.train_baseline()

        vector = np.array([[
            telemetry["cpu_usage"],
            telemetry["ram_usage"],
            telemetry["gpu_usage"],
            telemetry["temperature"],
            telemetry["active_tasks"]
        ]])

        # Isolation Forest prediction: 1 (Normal), -1 (Anomali)
        pred = self.model.predict(vector)[0]
        # decision_function: negatif değerler anomaliye yaklaştıkça büyür
        raw_score = float(self.model.decision_function(vector)[0])

        # Anomali risk skoru:
        # raw_score pozitif ise normal, negatif ise anomaliye doğru gider.
        # En yüksek z-skoru da hesaba katarak hassasiyeti artırıyoruz.
        deviations = self._calculate_feature_deviations(telemetry)
        max_abs_z = max(abs(z) for _, z in deviations)
        
        base_risk = (0.10 - raw_score) * 320.0
        z_boost = max(0.0, (max_abs_z - 2.0) * 12.0)
        risk_score = min(100.0, max(0.0, base_risk + z_boost))
        risk_score = round(risk_score, 1)

        is_anomaly = bool(pred == -1 or risk_score >= 55.0 or max_abs_z >= 3.0)
        primary_cause, primary_z = deviations[0]

        # Tedbir amaçlı bildirim metni üretme
        notification = self._generate_proactive_notification(
            is_anomaly, risk_score, deviations, telemetry
        )

        return {
            "is_anomaly": is_anomaly,
            "risk_score": risk_score,
            "raw_decision_score": round(raw_score, 4),
            "primary_driver": primary_cause,
            "primary_deviation_z": primary_z,
            "all_deviations": dict(deviations),
            "notification": notification
        }

    def _generate_proactive_notification(
        self, 
        is_anomaly: bool, 
        risk_score: float, 
        deviations: List[Tuple[str, float]], 
        telemetry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Aykırı değerin niteliğine göre proaktif eylem mesajı üretir."""
        
        ram = telemetry["ram_usage"]
        cpu = telemetry["cpu_usage"]
        gpu = telemetry["gpu_usage"]

        # 1. Normal Durum
        if not is_anomaly and risk_score < 38.0:
            return {
                "level": "INFO",
                "badge": "STABİL",
                "title": "Sistem Normal Aralıkta",
                "message": "Metrikler öğrenilen çalışma sınırları içerisinde seyrediyor.",
                "action": "Herhangi bir müdahaleye gerek yok."
            }

        # 2. Kritik / Anomali Durumu (Eşik aşımları ve yüksek risk)
        primary_cause = deviations[0][0]
        primary_z = deviations[0][1]

        if is_anomaly or risk_score >= 50.0:
            if ram > 80.0:
                return {
                    "level": "CRITICAL",
                    "badge": "OOM ÖNLEYİCİ ALARM",
                    "title": "Bellek Sızıntısı (Memory Leak) Riski!",
                    "message": f"RAM kullanımı kritik seviyeye (%{ram}) ulaştı. OOM Killer her an Servis B'yi durdurabilir.",
                    "action": "PROAKTİF EYLEM: Servis B yeni iş kabulünü derhal durdursun (Backpressure). Görevler Node-02'ye tahliye edilmeli (Pod Drain)."
                }
            elif cpu > 80.0 and gpu > 75.0:
                return {
                    "level": "CRITICAL",
                    "badge": "KAYNAK TÜKENME ALARMI",
                    "title": "Eşzamanlı CPU & GPU Darboğazı!",
                    "message": f"CPU (%{cpu}) ve GPU (%{gpu}) birlikte sınırda. Yanıt gecikmeleri katlanıyor.",
                    "action": "PROAKTİF EYLEM: Otomatik yatay ölçekleme (HPA - AutoScale) devreye sokulsun, batch görevleri duraklatılsın."
                }
            elif cpu > 80.0:
                return {
                    "level": "CRITICAL",
                    "badge": "GECİKME KORUMA ALARMI",
                    "title": "CPU Ani Sıçraması (CPU Burst)!",
                    "message": f"CPU %{cpu} seviyesine vurdu, istek kuyruğu şişiyor ve timeout riski mevcut.",
                    "action": "PROAKTİF EYLEM: İstek kuyruğunda 'Rate Limiting' aktif edilsin, önceliksiz arka plan cron görevleri askıya alınsın."
                }
            elif gpu > 80.0:
                return {
                    "level": "CRITICAL",
                    "badge": "CUDA OOM ALARMI",
                    "title": "GPU Aşırı Yükleme / VRAM Kilitlenmesi",
                    "message": f"GPU kullanımı %{gpu} seviyesinde. Yeni tensör hesaplamaları çökmek üzere.",
                    "action": "PROAKTİF EYLEM: Çıkarım (inference) batch boyutu küçültülsün, fan hızı %100'e çekilsin."
                }
            elif primary_cause == "ram_usage":
                return {
                    "level": "WARNING",
                    "badge": "BELLEK ARTIŞ UYARISI",
                    "title": "Kademeli Bellek Tırmanışı Tespit Edildi",
                    "message": f"RAM kullanımı (%{ram}) normal dağılımın dışına çıktı (+{primary_z}σ). Sızıntı (Leak) şüphesi var.",
                    "action": "PROAKTİF EYLEM: Bellek havuzu izlemeye alındı; tırmanış sürerse otomatik pod drenajı tetiklenecek."
                }
            elif primary_cause == "cpu_usage":
                return {
                    "level": "WARNING",
                    "badge": "CPU YÜK UYARISI",
                    "title": "CPU Tüketiminde Anormal Dalgalanma",
                    "message": f"CPU (%{cpu}) beklenen normdan saptı (+{primary_z}σ).",
                    "action": "PROAKTİF EYLEM: Süreç bazlı CPU tüketim profili analiz ediliyor."
                }
            elif primary_cause == "gpu_usage":
                return {
                    "level": "WARNING",
                    "badge": "GPU YÜK UYARISI",
                    "title": "GPU Yükünde Beklenmeyen Artış",
                    "message": f"GPU (%{gpu}) norm dışı aktivite sergiliyor (+{primary_z}σ).",
                    "action": "PROAKTİF EYLEM: İnferans ve model kuyruğu denetleniyor."
                }
            else:
                return {
                    "level": "CRITICAL",
                    "badge": "ÇOK DEĞİŞKENLİ ANOMALİ",
                    "title": "Beklenmeyen Metrik Kombinasyonu",
                    "message": f"Öğrenilen profilin dışında çoklu sapma tespit edildi (Risk: %{risk_score}). Başlıca etken: {primary_cause}.",
                    "action": "PROAKTİF EYLEM: Sistem sağlık kontrolü tetiklensin ve telemetri logları kaydedilsin."
                }

        # 3. Hafif Sapma (Early Warning)
        return {
            "level": "WARNING",
            "badge": "ERKEN UYARI",
            "title": "Hafif Sapma Gözlemlendi",
            "message": f"Metriklerde olağandışı kıpırdanma var (Risk: %{risk_score}). Başlıca etken: {deviations[0][0]}.",
            "action": "Kuyruk eşiği izleniyor; henüz yük kısıtlaması gerekmiyor."
        }
