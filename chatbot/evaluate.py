import csv
import requests
import time
from difflib import SequenceMatcher

API_URL = "http://localhost:5000/query"

def similarity(a, b):
    """Rough string similarity for automatic scoring."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def evaluate():
    with open("evaluation_questions.csv", newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        total, acc_score, rel_score, latencies = 0, 0, 0, []

        for row in reader:
            q = row["question"].strip()
            expected = row["expected_answer"].strip()

            t0 = time.time()
            res = requests.post(API_URL, json={"question": q}).json()
            latency = round(time.time() - t0, 3)
            latencies.append(latency)

            answer = res.get("answer", "").strip()
            sim = similarity(answer, expected)
            correct = sim > 0.6  # threshold for correctness

            print(f"\nQ: {q}\nA: {answer}\nExpected: {expected}\nSim={sim:.2f}  Latency={latency}s")

            # accuracy: 1 if fairly correct, else 0
            acc_score += 1 if correct else 0

            # relevance: crude heuristic based on non-empty + similarity
            rel_score += 1 if sim > 0.4 else 0

            total += 1

        print("\n=== SUMMARY ===")
        print(f"Questions: {total}")
        print(f"Accuracy: {acc_score/total:.2f}")
        print(f"Relevance: {rel_score/total:.2f}")
        print(f"Avg Latency: {sum(latencies)/len(latencies):.2f}s")

if __name__ == "__main__":
    evaluate()
