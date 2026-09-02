from dataclasses import dataclass

M = 60


@dataclass(frozen=True)
class Technique:
    key: str
    emoji: str
    name: str
    focus: int
    rest: int
    long_rest: int = 0
    cycle: int = 4
    ratio: int = 0
    min_rest: int = 3 * M
    max_rest: int = 30 * M
    about: str = ""


TECHNIQUES: list[Technique] = [
    Technique(
        "pomodoro", "\U0001F345", "Pomodoro", 25 * M, 5 * M, 15 * M, 4,
        about="Venticinque minuti su un compito solo, poi cinque di stacco; "
              "ogni quattro giri una pausa lunga. Nasce negli anni '80 da un "
              "timer da cucina a forma di pomodoro. Serve a rendere il tempo "
              "una cosa che vedi scorrere, e a spezzare i compiti grossi in "
              "pezzi che non fanno paura.",
    ),
    Technique(
        "5217", "⚡", "52 / 17", 52 * M, 17 * M,
        about="Cinquantadue minuti di lavoro pieno e diciassette di stacco "
              "vero. È il ritmo emerso dai dati di DeskTime osservando chi "
              "rendeva di più: poche pause, ma lunghe abbastanza da "
              "ricaricare davvero. Buona per una normale giornata al computer.",
    ),
    Technique(
        "ultradian", "\U0001F30A", "Ultradian", 90 * M, 20 * M,
        about="Novanta minuti seguono il ritmo ultradiano del cervello, lo "
              "stesso che scandisce il sonno: circa un'ora e mezza di "
              "attenzione, poi un calo fisiologico. È la tecnica del lavoro "
              "profondo — partire costa di più, ma arrivi molto più a fondo.",
    ),
    Technique(
        "flowtime", "\U0001F300", "Flowtime", 0, 0, ratio=5,
        about="Nessun timer che ti interrompe: il cronometro sale e sei tu a "
              "fermarlo quando senti che stai calando. La pausa la calcola "
              "sul lavoro fatto, un quinto del tempo. Pensata per chi viene "
              "buttato fuori dalla concentrazione da una campanella.",
    ),
    Technique(
        "animedoro", "\U0001F3AC", "Animedoro", 40 * M, 20 * M,
        about="Quaranta minuti di lavoro e venti di pausa lunga e piacevole, "
              "il tempo di un episodio. La ricompensa è abbastanza grande da "
              "farti venire voglia di arrivarci: funziona bene la sera e "
              "quando il compito è noioso.",
    ),
]
def schema(t: Technique) -> str:
    """Riga che riassume le durate della tecnica."""
    if t.ratio:
        return (
            f"pausa = lavoro ÷ {t.ratio}, "
            f"da {t.min_rest // M} a {t.max_rest // M} min"
        )

    parts = [
        f"{t.focus // M} min focus",
        f"{t.rest // M} pausa",
    ]

    if t.long_rest:
        parts.append(f"{t.long_rest // M} lunga ogni {t.cycle}")

    return " · ".join(parts)

def is_minutes_field(attr: str) -> bool:
    return attr in {
        "focus",
        "rest",
        "long_rest",
        "min_rest",
        "max_rest",
    }