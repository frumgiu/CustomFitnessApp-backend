from typing import Any, Literal

# Esponente di Riegel per la corsa
_RIEGEL_EXP = 1.06


def predict_race_time(
    activities: list[dict[str, Any]],
    distance_km: float,
) -> dict[str, Any]:
    """Prevede il tempo gara per distance_km a partire da attività recenti.

    Algoritmo:
    1. Filtra le run con distanza > 5 km, prende le 10 più recenti.
    2. Per ogni run applica la formula di Riegel verso la distanza target:
           T2 = T1 * (D2 / D1) ^ 1.06
    3. Calcola la media ponderata dei tempi previsti (peso lineare: più
       recente = peso maggiore).

    Ritorna un dict con:
        distance_km, predicted_seconds, predicted_time, confidence, based_on
    oppure {"error": <messaggio>} se i dati sono insufficienti.
    """
    # Filtra run valide con distanza > 5 km
    valid = [
        a for a in activities
        if a.get("distance") and a["distance"] > 5000
        and a.get("moving_time") and a["moving_time"] > 0
    ]

    # Ordina per data decrescente e limita a 10
    valid.sort(key=lambda a: a.get("start_date", ""), reverse=True)
    runs = valid[:10]

    n = len(runs)
    if n == 0:
        return {"error": "Dati insufficienti: nessuna run con distanza > 5 km trovata."}

    # Pesi lineari decrescenti: run più recente peso n, più vecchia peso 1
    weights = [float(n - i) for i in range(n)]
    total_weight = sum(weights)

    # Applica Riegel da ogni attività verso la distanza target
    predicted_times: list[float] = []
    for run in runs:
        d1_km = run["distance"] / 1000.0
        t1 = float(run["moving_time"])
        t2 = t1 * (distance_km / d1_km) ** _RIEGEL_EXP
        predicted_times.append(t2)

    predicted_seconds = round(
        sum(w * t for w, t in zip(weights, predicted_times)) / total_weight
    )

    # Livello di confidenza
    confidence: Literal["low", "medium", "high"]
    if n >= 8:
        confidence = "high"
    elif n >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    # Formatta il tempo previsto
    h = predicted_seconds // 3600
    m = (predicted_seconds % 3600) // 60
    s = predicted_seconds % 60
    if h > 0:
        predicted_time = f"{h}:{m:02d}:{s:02d}"
    else:
        predicted_time = f"{m}:{s:02d}"

    return {
        "distance_km": distance_km,
        "predicted_seconds": predicted_seconds,
        "predicted_time": predicted_time,
        "confidence": confidence,
        "based_on": n,
    }
