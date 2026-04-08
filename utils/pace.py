def speed_to_pace(speed_mps: float) -> str:
    """Converte velocità (m/s) in pace (min/km) nel formato 'M:SS'."""
    if speed_mps <= 0:
        return "--:--"
    pace_seconds = 1000 / speed_mps
    minutes = int(pace_seconds // 60)
    seconds = int(pace_seconds % 60)
    return f"{minutes}:{seconds:02d}"


def format_distance(meters: float) -> str:
    """Formatta distanza in km con un decimale."""
    return f"{meters / 1000:.1f} km"


def format_duration(seconds: int) -> str:
    """Formatta durata in 'H:MM:SS' o 'M:SS'."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_elevation(meters: float) -> str:
    """Formatta dislivello in metri arrotondato."""
    return f"{round(meters)} m"
