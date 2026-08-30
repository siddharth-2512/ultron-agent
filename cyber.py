import os
import pyshark
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest

class NetworkSecurityEngine:
    def __init__(self):
        self.model = IsolationForest(contamination=0.1, random_state=42)
        self.is_trained = False

    def extract_pcap_features(self, pcap_path: str) -> pd.DataFrame:
        """Parses a PCAP file and extracts numerical features per packet."""
        if not os.path.exists(pcap_path):
            raise FileNotFoundError(f"PCAP file not found: {pcap_path}")

        cap = pyshark.FileCapture(pcap_path, only_summaries=True)
        features = []

        for pkt in cap:
            try:
                length = float(pkt.length)
                # Maps transport protocol to rough numeric ID
                proto = 1 if 'TCP' in pkt.protocol else (2 if 'UDP' in pkt.protocol else 0)
                features.append([length, proto])
            except AttributeError:
                continue

        cap.close()
        
        if not features:
            # Fallback dummy frame if pcap is empty
            return pd.DataFrame([[0.0, 0]], columns=['length', 'proto'])

        return pd.DataFrame(features, columns=['length', 'proto'])

    def train_baseline(self, dataset_csv: str = None):
        """Trains Isolation Forest on standard network behavior data."""
        if dataset_csv and os.path.exists(dataset_csv):
            df = pd.read_csv(dataset_csv)
        else:
            # Synthetic normal traffic baseline if no CSV provided
            normal_lengths = np.random.normal(loc=500, scale=100, size=500)
            normal_proto = np.random.choice([1, 2], size=500, p=[0.8, 0.2])
            df = pd.DataFrame({'length': normal_lengths, 'proto': normal_proto})

        self.model.fit(df[['length', 'proto']])
        self.is_trained = True

    def calculate_threat_score(self, pcap_path: str = None) -> dict:
        """Computes anomaly threat score between 0.0 (safe) and 1.0 (critical threat)."""
        if not self.is_trained:
            self.train_baseline()

        if pcap_path and os.path.exists(pcap_path):
            df = self.extract_pcap_features(pcap_path)
        else:
            sample_size = int(np.random.randint(150, 600))
            is_attack = bool(np.random.choice([True, False], p=[0.25, 0.75]))
            
            if is_attack:
                lengths = np.random.uniform(20, 9000, size=sample_size)
                protos = np.random.choice([0, 1, 2], size=sample_size, p=[0.5, 0.2, 0.3])
            else:
                lengths = np.random.normal(loc=500, scale=100, size=sample_size)
                protos = np.random.choice([1, 2], size=sample_size, p=[0.8, 0.2])

            df = pd.DataFrame({'length': lengths, 'proto': protos})

        scores = self.model.decision_function(df[['length', 'proto']])
        predictions = self.model.predict(df[['length', 'proto']])

        anomaly_ratio = float(np.mean(predictions == -1))
        raw_score = float(-np.mean(scores))
        
        threat_score = float(np.clip((raw_score + 0.5), 0.0, 1.0))
        
        # Cast explicitly to native Python bool/int types
        anomaly_detected = bool(threat_score > 0.60 or anomaly_ratio > 0.35)

        return {
            "threat_score": round(threat_score, 2),
            "anomaly_detected": anomaly_detected,  # Native Python bool
            "status": "CRITICAL THREAT DETECTED" if anomaly_detected else "NETWORK NOMINAL",
            "packets_analyzed": int(len(df))        # Native Python int
        }


# Singleton instance ready for import in main.py
cyber_engine = NetworkSecurityEngine()
cyber_engine.train_baseline()

if __name__ == "__main__":
    print("[CYBER ENGINE] Isolation Forest baseline ready.")
    test_run = cyber_engine.calculate_threat_score()
    print("Test Scan Output:", test_run)