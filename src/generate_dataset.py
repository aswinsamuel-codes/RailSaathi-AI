"""
Synthetic Rail Madad complaint dataset generator.

Real Rail Madad complaints are not publicly released, so a realistic
synthetic dataset is simulated. The simulation is driven by a latent
"condition" process for every train, so that the data contain the
patterns a real system would show:

  * 13 complaint categories (as used on the Rail Madad portal) mapped to
    7 responsible departments, with 4 severity levels
  * multimodal inputs: typed text, OCR text from photos, tags from an
    image-recognition model (simulated, imperfect), and speech-to-text
    (ASR) transcripts of audio complaints, plus EXIF/GPS metadata
  * noisy language: Hinglish, SMS spelling, typos, mixed complaints,
    vague complaints and a small fraction of label noise
  * seasonality (summer AC/water failures, monsoon leakage, winter fog
    delays, festival crowding) and trains whose condition deteriorates
  * multi-passenger incidents (several people reporting the same fault)
  * resolution time, SLA breach, feedback text and rating

Output: data/raw/rail_madad_complaints.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "rail_madad_complaints.csv"
rng = np.random.default_rng(2026)

START, END = pd.Timestamp("2025-01-01"), pd.Timestamp("2026-09-30 23:59")
SEVERITIES = ["Critical", "High", "Medium", "Low"]
SLA_HOURS = {"Critical": 1, "High": 4, "Medium": 12, "Low": 48}

# category: (department, base share, severity distribution C/H/M/L)
CATEGORIES = {
    "Medical Assistance":    ("Medical",         0.04, [0.45, 0.40, 0.15, 0.00]),
    "Security":              ("RPF",             0.06, [0.25, 0.45, 0.25, 0.05]),
    "Women Safety":          ("RPF",             0.025, [0.40, 0.45, 0.15, 0.00]),
    "Divyangjan Facilities": ("Commercial",      0.02, [0.00, 0.30, 0.50, 0.20]),
    "Coach Cleanliness":     ("Mechanical",      0.16, [0.00, 0.10, 0.55, 0.35]),
    "Water Availability":    ("Mechanical",      0.11, [0.00, 0.35, 0.50, 0.15]),
    "Electrical Equipment":  ("Electrical",      0.12, [0.05, 0.35, 0.45, 0.15]),
    "Coach Maintenance":     ("Mechanical",      0.09, [0.03, 0.22, 0.50, 0.25]),
    "Catering & Vending":    ("IRCTC Catering",  0.10, [0.00, 0.10, 0.50, 0.40]),
    "Staff Behaviour":       ("Commercial",      0.07, [0.00, 0.25, 0.50, 0.25]),
    "Punctuality":           ("Operating",       0.10, [0.00, 0.10, 0.40, 0.50]),
    "Bed Roll":              ("Mechanical",      0.055, [0.00, 0.00, 0.35, 0.65]),
    "Refund & Ticketing":    ("Commercial",      0.05, [0.00, 0.05, 0.40, 0.55]),
}
CATS = list(CATEGORIES)

# Issue phrases per category and severity level ("C", "H", "M", "L").
# {coach}, {hrs}, {stn}, {amt} are filled at generation time.
PHRASES = {
    "Medical Assistance": {
        "C": ["my father is having severe chest pain and sweating", "a passenger has fainted and is unconscious",
              "pregnant lady in labour pain, need doctor immediately", "elderly passenger fell down and is bleeding from head",
              "child is having fits and not responding", "passenger having breathing problem, asthma attack"],
        "H": ["need a doctor at next station, my mother has high fever", "my wife is vomiting continuously since {hrs} hours",
              "diabetic passenger feeling dizzy, sugar level low", "small kid has high fever, need medicine urgently",
              "passenger has severe stomach pain"],
        "M": ["need first aid kit for a small cut on hand", "require a pain killer for headache",
              "need doctor to check my BP at next station", "minor injury while boarding, need first aid"],
    },
    "Security": {
        "C": ["my bag was snatched and the thief is still in the coach", "group of drunk men fighting with knife in coach {coach}",
              "armed persons threatening passengers", "stone pelting on the train, window glass broken and people hurt"],
        "H": ["my mobile phone was stolen while sleeping", "my luggage has been stolen from under the berth",
              "unauthorized persons occupying reserved berths and threatening us", "drunk passenger misbehaving with everyone",
              "chain snatching happened near the door"],
        "M": ["unknown persons travelling without ticket in reserved coach", "suspicious unattended bag lying near the door",
              "hawkers forcefully entering the coach", "beggars troubling passengers continuously"],
        "L": ["no RPF staff seen in the train during the night", "door of coach not locked at night, feeling unsafe"],
    },
    "Women Safety": {
        "C": ["a man is harassing a girl travelling alone in coach {coach}", "someone touched me inappropriately, please send help",
              "a group of men passing lewd comments and following me", "woman passenger being stalked, she is scared"],
        "H": ["men occupying the ladies compartment and refusing to leave", "a man keeps staring and taking photos of women",
              "girl travelling alone feeling unsafe due to drunk co-passenger"],
        "M": ["no lady constable in the train", "ladies coach has male passengers sitting"],
    },
    "Divyangjan Facilities": {
        "H": ["wheelchair not provided for my disabled father at the station", "divyang passenger not able to board, no ramp available",
              "blind passenger needs assistance to get down at {stn}"],
        "M": ["divyang coach is locked and we are not allowed to enter", "battery car not available for elderly and disabled",
              "disabled friendly toilet is not working", "lower berth not given to handicapped passenger"],
        "L": ["braille signage missing in the coach", "no help desk for divyangjan at the station"],
    },
    "Coach Cleanliness": {
        "H": ["toilet is overflowing and smell is unbearable in the whole coach", "cockroaches and rats roaming everywhere in coach {coach}",
              "vomit and garbage lying on floor since boarding"],
        "M": ["toilet is very dirty and stinking", "coach floor is full of garbage and food waste", "dustbin is overflowing",
              "cockroaches in the berth", "washbasin is choked and dirty", "coach not cleaned since {hrs} hours"],
        "L": ["windows are very dusty", "seats are dirty and stained", "please arrange coach cleaning",
              "cleaning staff did not come for on board housekeeping"],
    },
    "Water Availability": {
        "H": ["no water in toilets since {hrs} hours", "water tank is empty in coach {coach}, very difficult for passengers",
              "no water in the entire coach, children are suffering"],
        "M": ["water not coming in the wash basin", "no water in the toilet tap", "water supply stopped in coach {coach}",
              "drinking water not available in the train"],
        "L": ["water pressure is very low in the tap", "water cooler not working at the platform"],
    },
    "Electrical Equipment": {
        "C": ["smoke coming from the electrical panel near the door", "sparks and burning smell from switch board in coach {coach}",
              "short circuit and small fire near charging point"],
        "H": ["AC is not working since {hrs} hours, it is very hot", "AC stopped completely and passengers are suffocating",
              "all lights and fans are off in coach {coach}", "AC is not cooling at all in this heat"],
        "M": ["fan is not working at my berth", "charging point not working", "AC is leaking water on the berth",
              "light not working in the toilet", "AC temperature is too cold and cannot be adjusted"],
        "L": ["reading light not working", "mobile charging socket is loose", "night lamp is not working"],
    },
    "Coach Maintenance": {
        "C": ["coach door is not closing and train is running fast", "berth chain broken, berth fell on a passenger"],
        "H": ["window glass broken, rain water coming inside", "toilet door broken, cannot be locked", "roof is leaking heavily on the seats",
              "emergency window is jammed"],
        "M": ["middle berth chain is broken", "window shutter is not closing", "toilet tap is broken", "seat cushion is torn",
              "snack table is broken", "curtain rod is broken"],
        "L": ["mirror is broken in washroom", "bottle holder is missing", "ladder of upper berth is loose"],
    },
    "Catering & Vending": {
        "H": ["food served was stale and many passengers fell sick", "found an insect in the food packet", "food poisoning after eating train meal"],
        "M": ["food quality is very bad and cold", "vendor charging more than MRP, asked Rs {amt} for water bottle",
              "pantry staff not giving bill for the food", "ordered food not delivered", "tea was stale and tasteless"],
        "L": ["food quantity is very less", "no veg option available in pantry", "pantry car closed early",
              "e-catering order delivered late"],
    },
    "Staff Behaviour": {
        "H": ["TTE is demanding bribe for confirming berth", "TTE asking Rs {amt} without receipt",
              "coach attendant was very rude and abusive to my family"],
        "M": ["TTE is not available in the coach", "attendant refused to give bedsheet and spoke rudely",
              "staff sleeping and not responding", "railway staff misbehaved at enquiry counter"],
        "L": ["staff not wearing name badge", "attendant not helping passengers", "TTE did not check tickets"],
    },
    "Punctuality": {
        "H": ["train is stuck for {hrs} hours without any information", "train detained in the middle of nowhere, no food or water"],
        "M": ["train is running {hrs} hours late", "train delayed again, will miss my connecting train",
              "train stopped at outer signal for very long"],
        "L": ["train is slightly late every day", "running status not updated on NTES", "platform changed without announcement"],
    },
    "Bed Roll": {
        "M": ["bedsheet and blanket not provided in AC coach", "blanket is smelling very bad", "pillow cover is dirty and stained"],
        "L": ["bedroll given is torn", "towel not given", "bedsheet is wet", "bedroll is not properly washed"],
    },
    "Refund & Ticketing": {
        "H": ["double money deducted for ticket but no refund", "ticket cancelled automatically, money not refunded"],
        "M": ["TDR filed {hrs} days ago, refund not received", "refund amount less than expected",
              "berth allotted to two passengers on same seat"],
        "L": ["unable to change boarding station", "wrong name printed on ticket", "waiting list status not updating"],
    },
}

HINGLISH = {
    "Coach Cleanliness": ["toilet bahut ganda hai", "coach me bahut kachra pada hai", "safai nahi hui hai", "bahut badbu aa rahi hai"],
    "Water Availability": ["toilet me pani nahi hai", "pani nahi aa raha hai coach me", "{hrs} ghante se pani nahi hai"],
    "Electrical Equipment": ["AC kaam nahi kar raha", "pankha nahi chal raha", "light band hai coach me", "AC bilkul thanda nahi kar raha"],
    "Catering & Vending": ["khana bahut kharab hai", "vendor zyada paise le raha hai", "chai thandi aur bekar hai"],
    "Staff Behaviour": ["TT paise maang raha hai", "attendant badtameezi kar raha hai", "TT seat ke liye rishwat maang raha hai"],
    "Punctuality": ["train {hrs} ghante late hai", "train bahut der se ruki hui hai"],
    "Security": ["mera phone chori ho gaya", "mera bag chori ho gaya", "sharabi log jhagda kar rahe hai"],
    "Medical Assistance": ["mere papa ki tabiyat bahut kharab hai doctor chahiye", "bacche ko tez bukhar hai"],
    "Women Safety": ["ek aadmi ladki ko pareshan kar raha hai", "ladies coach me aadmi baithe hai"],
    "Bed Roll": ["chadar aur kambal nahi diya", "kambal ganda hai"],
    "Coach Maintenance": ["khidki tooti hui hai", "toilet ka darwaza toota hai", "chhat se pani tapak raha hai"],
    "Refund & Ticketing": ["refund abhi tak nahi aaya", "paise kat gaye ticket nahi bana"],
    "Divyangjan Facilities": ["wheelchair nahi mila", "divyang coach band hai"],
}

# What a (simulated) image-recognition model returns for photos/videos.
VISION_TAGS = {
    "Medical Assistance": ["person lying", "crowd", "person sitting"],
    "Security": ["broken glass", "crowd", "person standing", "luggage"],
    "Women Safety": ["crowd", "person standing", "person sitting"],
    "Divyangjan Facilities": ["wheelchair", "platform", "door"],
    "Coach Cleanliness": ["garbage", "dirty floor", "dirty toilet", "dustbin", "insects"],
    "Water Availability": ["water tap", "wash basin", "toilet"],
    "Electrical Equipment": ["fan", "ac vent", "light fixture", "switch board", "smoke"],
    "Coach Maintenance": ["broken window", "broken berth", "door", "water leakage", "broken fitting"],
    "Catering & Vending": ["food tray", "food packet", "bill", "water bottle"],
    "Staff Behaviour": ["person in uniform", "person standing"],
    "Punctuality": ["station board", "platform", "display board"],
    "Bed Roll": ["bedsheet", "blanket", "pillow"],
    "Refund & Ticketing": ["ticket", "screenshot", "bill"],
}
ALL_TAGS = sorted({t for v in VISION_TAGS.values() for t in v})

OPENERS = ["", "", "", "Sir, ", "Respected sir, ", "Hello Rail Madad, ", "@RailMinIndia ", "Please help, ",
           "Urgent: ", "Dear team, ", "Complaint: ", "Pls look into this. "]
CLOSERS = ["", "", "", " Please take action.", " Kindly help asap.", " Very disappointed.", " Pathetic service.",
           " Please do the needful.", " Thank you.", " Expecting quick action.", " This is unacceptable!!"]
SMS = {"please": "pls", "you": "u", "not": "nt", "working": "wrkng", "coach": "coch", "since": "snce",
       "hours": "hrs", "urgent": "urgnt", "train": "trn", "water": "watr", "help": "hlp"}

STATIONS = {  # code: (name, lat, lon)
    "NDLS": ("New Delhi", 28.6430, 77.2194), "CSMT": ("Mumbai CSMT", 18.9402, 72.8356),
    "HWH": ("Howrah", 22.5839, 88.3426), "MAS": ("Chennai Central", 13.0827, 80.2757),
    "SBC": ("Bengaluru", 12.9784, 77.5695), "SC": ("Secunderabad", 17.4337, 78.5016),
    "LKO": ("Lucknow", 26.8317, 80.9196), "PNBE": ("Patna", 25.6022, 85.1376),
    "JP": ("Jaipur", 26.9196, 75.7878), "ADI": ("Ahmedabad", 23.0258, 72.6009),
    "BPL": ("Bhopal", 23.2665, 77.4129), "NGP": ("Nagpur", 21.1520, 79.0884),
    "GHY": ("Guwahati", 26.1817, 91.7514), "BBS": ("Bhubaneswar", 20.2650, 85.8434),
    "ERS": ("Ernakulam", 9.9696, 76.2905), "CDG": ("Chandigarh", 30.7023, 76.8216),
    "PUNE": ("Pune", 18.5285, 73.8743), "BSB": ("Varanasi", 25.3264, 82.9870),
    "ASR": ("Amritsar", 31.6328, 74.8673), "VSKP": ("Visakhapatnam", 17.7215, 83.2905),
}
ZONE_OF = {"NDLS": "NR", "CSMT": "CR", "HWH": "ER", "MAS": "SR", "SBC": "SWR", "SC": "SCR", "LKO": "NR",
           "PNBE": "ECR", "JP": "NWR", "ADI": "WR", "BPL": "WCR", "NGP": "CR", "GHY": "NFR", "BBS": "ECoR",
           "ERS": "SR", "CDG": "NR", "PUNE": "CR", "BSB": "NER", "ASR": "NR", "VSKP": "ECoR"}
TRAIN_TYPES = {  # type: (share, coach codes, AC?)
    "Rajdhani": (0.12, ["A1", "B1", "B2", "B3", "B4", "B5", "B6", "H1"], True),
    "Shatabdi": (0.10, ["C1", "C2", "C3", "C4", "C5", "E1"], True),
    "Vande Bharat": (0.10, ["C1", "C2", "C3", "C4", "C5", "C6", "E1"], True),
    "Superfast Express": (0.30, ["S1", "S2", "S3", "S4", "S5", "S6", "B1", "B2", "B3", "A1", "GEN"], False),
    "Mail/Express": (0.30, ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "B1", "B2", "GEN"], False),
    "Passenger": (0.08, ["GEN", "D1", "D2"], False),
}
CHANNELS = ["RailMadad App", "Web Portal", "Helpline 139", "X (Twitter)", "WhatsApp"]
CHANNEL_P = [0.38, 0.17, 0.25, 0.12, 0.08]


# ---------------------------------------------------------------------------
def make_trains(n=60) -> pd.DataFrame:
    types = list(TRAIN_TYPES)
    p = np.array([TRAIN_TYPES[t][0] for t in types])
    codes = list(STATIONS)
    rows, used = [], set()
    for i in range(n):
        tt = rng.choice(types, p=p / p.sum())
        src, dst = rng.choice(codes, 2, replace=False)
        num = int(rng.integers(12001, 22999))
        while num in used:
            num = int(rng.integers(12001, 22999))
        used.add(num)
        rows.append({"train_no": str(num), "train_type": tt, "source": src, "destination": dst,
                     "zone": ZONE_OF[src], "age_years": int(rng.integers(1, 30)) if tt != "Vande Bharat" else int(rng.integers(0, 4)),
                     "popularity": float(rng.lognormal(0, 0.45))})
    return pd.DataFrame(rows)


def seasonal_factor(cat: str, ts: pd.Timestamp) -> float:
    m = ts.month
    f = 1.0
    if cat in ("Electrical Equipment", "Water Availability") and m in (4, 5, 6):
        f *= 1.8
    if cat == "Coach Maintenance" and m in (7, 8, 9):
        f *= 1.6  # monsoon leakage
    if cat == "Punctuality" and m in (12, 1):
        f *= 2.2  # winter fog
    if cat in ("Security", "Coach Cleanliness", "Refund & Ticketing") and m in (10, 11, 3):
        f *= 1.4  # festival rush
    if cat == "Bed Roll" and m in (11, 12, 1, 2):
        f *= 1.5
    return f


def add_typos(text: str, rate: float) -> str:
    words = text.split()
    out = []
    for w in words:
        lw = w.lower().strip(".,!")
        if lw in SMS and rng.random() < 0.5:
            out.append(SMS[lw])
            continue
        if len(w) > 3 and rng.random() < rate:
            i = int(rng.integers(1, len(w) - 1))
            op = rng.integers(3)
            w = w[:i] + w[i + 1:] if op == 0 else (w[:i] + w[i] + w[i:] if op == 1 else w[:i - 1] + w[i] + w[i - 1] + w[i + 1:])
        out.append(w)
    return " ".join(out)


def fill(template: str, coach: str, stn: str) -> str:
    return template.format(coach=coach, hrs=int(rng.integers(2, 13)), stn=STATIONS[stn][0],
                           amt=int(rng.choice([20, 50, 100, 200, 500])))


def pick_phrase(cat: str, sev: str) -> str:
    bank = PHRASES[cat]
    level = sev[0]
    order = {"C": "CHML", "H": "HMCL", "M": "MHLC", "L": "LMH C"}[level].replace(" ", "")
    for lv in order:
        if lv in bank:
            return str(rng.choice(bank[lv]))
    raise ValueError(cat)


def compose_text(cat, sev, train, coach, stn, pnr, media, second_cat):
    """Build the complainant's text (or ASR transcript for audio)."""
    hinglish = cat in HINGLISH and rng.random() < 0.18
    core = fill(str(rng.choice(HINGLISH[cat])) if hinglish else pick_phrase(cat, sev), coach, stn)
    parts = [str(rng.choice(OPENERS)) + core]
    ctx = rng.random()
    if ctx < 0.35:
        parts.append(f"in train {train['train_no']} coach {coach}")
    elif ctx < 0.55:
        parts.append(f"PNR {pnr}, coach {coach} seat {int(rng.integers(1, 73))}")
    elif ctx < 0.65:
        parts.append(f"train no {train['train_no']} near {STATIONS[stn][0]}")
    if second_cat is not None:  # mixed complaint: a minor second issue
        parts.append("also " + fill(pick_phrase(second_cat, "Low"), coach, stn))
    if sev == "Critical" and rng.random() < 0.4:
        parts.append(str(rng.choice(["emergency!!", "please send help immediately", "very serious situation"])))
    text = ", ".join(parts) + str(rng.choice(CLOSERS))
    if media == "audio":  # ASR transcript: lower case, no punctuation, more errors
        text = add_typos(text.lower().replace(",", "").replace("!", "").replace(".", ""), 0.12)
    elif rng.random() < 0.3:
        text = add_typos(text, 0.15)
    return text, hinglish


def make_ocr(cat, train, coach, pnr):
    """Text an OCR engine might read from the attached photo."""
    r = rng.random()
    if cat == "Catering & Vending" and r < 0.5:
        return f"MRP Rs {int(rng.choice([15, 20, 50, 70]))} PACKAGED DRINKING WATER" if r < 0.25 else f"IRCTC BILL TOTAL Rs {int(rng.integers(80, 400))}"
    if cat == "Refund & Ticketing" and r < 0.7:
        return f"PNR NO {pnr} TRAIN {train['train_no']} STATUS CNF"
    if cat == "Punctuality" and r < 0.6:
        return f"TRAIN {train['train_no']} EXPECTED {int(rng.integers(1, 12))}:{int(rng.integers(0, 6))}0 LATE"
    if r < 0.6:
        return f"{coach} {train['train_no']}" if r < 0.4 else f"{coach} / {int(rng.integers(1, 73))}"
    if r < 0.7:
        return str(rng.choice(["TOILET", "EMERGENCY WINDOW", "NO SMOKING", "DUSTBIN", "CHARGING POINT"]))
    return ""


def make_vision_tags(cat):
    """Simulated output of an image classifier: right ~70% of the time."""
    tags = list(rng.choice(VISION_TAGS[cat], size=min(2, len(VISION_TAGS[cat])), replace=False)) if rng.random() < 0.7 else []
    tags += list(rng.choice(ALL_TAGS, size=int(rng.integers(0, 2)), replace=False))
    return "|".join(sorted(set(tags)))


# ---------------------------------------------------------------------------
def simulate():
    trains = make_trains()
    weeks = pd.date_range(START, END, freq="W-MON")
    base_share = np.array([CATEGORIES[c][1] for c in CATS])
    base_share = base_share / base_share.sum()

    # Latent condition of every train x category: log-AR(1) random walk.
    # A few trains deteriorate steadily (the targets of predictive maintenance).
    n_t, n_c = len(trains), len(CATS)
    latent = np.zeros((n_t, n_c))
    deteriorating = rng.choice(n_t, 8, replace=False)
    age_effect = (trains["age_years"].values / 30.0)[:, None] * np.array(
        [1.0 if CATEGORIES[c][0] in ("Mechanical", "Electrical") else 0.2 for c in CATS])[None, :]
    target_total = 11500
    weekly_scale = target_total / len(weeks)

    rows = []
    cid = 0
    incident_id = 0
    for w_i, wk in enumerate(weeks):
        latent = 0.85 * latent + rng.normal(0, 0.25, latent.shape)
        drift = np.zeros_like(latent)
        drift[deteriorating] = 0.9 * w_i / len(weeks)
        mult = np.exp(latent + drift + 0.8 * age_effect)
        season = np.array([seasonal_factor(c, wk + pd.Timedelta(days=3)) for c in CATS])
        lam = weekly_scale * trains["popularity"].values[:, None] / trains["popularity"].sum() * base_share[None, :] * season[None, :] * mult
        counts = rng.poisson(lam)
        for ti, ci in zip(*np.nonzero(counts)):
            for _ in range(counts[ti, ci]):
                ts = wk + pd.Timedelta(minutes=int(rng.integers(0, 7 * 24 * 60)))
                if ts > END:
                    continue
                # more complaints in the evening / night of long-distance journeys
                hour_shift = int(rng.choice(range(24), p=_hour_p()))
                ts = ts.normalize() + pd.Timedelta(hours=hour_shift, minutes=int(rng.integers(0, 60)))
                group = 1
                cat = CATS[ci]
                if cat in ("Electrical Equipment", "Water Availability", "Coach Cleanliness", "Punctuality",
                           "Security", "Coach Maintenance") and rng.random() < 0.12:
                    group = int(rng.integers(2, 6))  # multi-passenger incident
                incident_id += 1
                train = trains.iloc[ti]
                coach = str(rng.choice(TRAIN_TYPES[train["train_type"]][1]))
                sev = str(rng.choice(SEVERITIES, p=CATEGORIES[cat][2]))
                for g in range(group):
                    cid += 1
                    rows.append(_complaint(cid, incident_id, ts + pd.Timedelta(minutes=int(rng.integers(0, 150)) * (g > 0)),
                                           train, coach, cat, sev))
    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df["complaint_id"] = [f"RM{2500000 + i:07d}" for i in range(len(df))]
    df["deteriorating_train"] = df["train_no"].isin(trains.iloc[deteriorating]["train_no"]).astype(int)
    return df, trains


_HOUR_P = None


def _hour_p():
    global _HOUR_P
    if _HOUR_P is None:
        h = np.arange(24)
        p = 0.6 + 0.8 * np.exp(-((h - 21) ** 2) / 18) + 0.6 * np.exp(-((h - 9) ** 2) / 12) + 0.3 * np.exp(-((h - 14) ** 2) / 10)
        _HOUR_P = p / p.sum()
    return _HOUR_P


def _complaint(cid, inc, ts, train, coach, cat, sev):
    stn = str(rng.choice([train["source"], train["destination"], rng.choice(list(STATIONS))]))
    pnr = str(rng.integers(2_000_000_000, 8_999_999_999))
    media = str(rng.choice(["text", "photo", "video", "audio"], p=[0.52, 0.31, 0.10, 0.07]))
    channel = "Helpline 139" if media == "audio" else str(rng.choice(CHANNELS, p=CHANNEL_P))
    second = str(rng.choice([c for c in CATS if c != cat])) if rng.random() < 0.15 else None
    text, hinglish = compose_text(cat, sev, train, coach, stn, pnr, media, second)

    vague = rng.random() < 0.04
    if vague:  # vague complaint with no clear cue -> irreducible error
        text = str(rng.choice(["very bad experience in this train, please look into it",
                               "worst journey ever, nobody is responding", "problem in coach " + coach + " please help",
                               "pls check my complaint urgently", "railway service is pathetic"]))
    label = cat if rng.random() > 0.03 else str(rng.choice(CATS))  # 3 % annotation noise

    has_img = media in ("photo", "video")
    ocr = make_ocr(cat, train, coach, pnr) if has_img else ""
    tags = make_vision_tags(cat) if has_img else ""
    exif_lag = float(np.round(rng.exponential(25), 1)) if has_img else np.nan
    lat = lon = np.nan
    if has_img and rng.random() < 0.65:  # GPS present in EXIF
        _, la, lo = STATIONS[stn]
        lat, lon = la + rng.normal(0, 0.3), lo + rng.normal(0, 0.3)

    # ---- resolution process ----------------------------------------------
    dept = CATEGORIES[label][0]
    dept_speed = {"Medical": 0.5, "RPF": 0.7, "Electrical": 1.4, "Mechanical": 1.6, "IRCTC Catering": 1.2,
                  "Commercial": 2.0, "Operating": 2.4}[dept]
    sev_speed = {"Critical": 0.35, "High": 1.0, "Medium": 2.6, "Low": 6.0}[sev]
    zone_eff = {"NR": 1.15, "CR": 0.95, "WR": 0.85, "SR": 0.8, "ER": 1.2, "ECR": 1.35, "NFR": 1.3}.get(train["zone"], 1.0)
    night = 1.35 if ts.hour >= 22 or ts.hour < 6 else 1.0
    evidence = 0.8 if has_img else 1.0
    vague_pen = 1.6 if vague else 1.0
    res_h = float(np.round(2.0 * dept_speed * sev_speed * zone_eff * night * evidence * vague_pen
                           * rng.lognormal(0, 0.75), 2))
    sla_breach = int(res_h > SLA_HOURS[sev])

    # ---- feedback -----------------------------------------------------------
    gave_fb = rng.random() < 0.6
    rating = np.nan
    fb = ""
    if gave_fb:
        ratio = res_h / SLA_HOURS[sev]
        score = 4.7 - 1.6 * np.log1p(ratio) - (0.6 if sev in ("Critical", "High") and sla_breach else 0) + rng.normal(0, 0.7)
        rating = int(np.clip(np.round(score), 1, 5))
        fb = _feedback(rating)

    return {
        "timestamp": ts, "incident_id": f"INC{inc:06d}", "channel": channel, "media_type": media,
        "complaint_text": text, "is_hinglish": int(hinglish), "ocr_text": ocr, "vision_tags": tags,
        "exif_capture_lag_min": exif_lag, "gps_lat": lat, "gps_lon": lon,
        "train_no": train["train_no"], "train_type": train["train_type"], "zone": train["zone"],
        "train_age_years": train["age_years"], "coach": coach, "pnr": pnr, "nearest_station": stn,
        "category": label, "department": dept, "severity": sev,
        "resolution_hours": res_h, "sla_hours": SLA_HOURS[sev], "sla_breached": sla_breach,
        "feedback_rating": rating, "feedback_text": fb,
    }


FB = {
    5: ["very quick response, thank you rail madad", "excellent service, issue solved within minutes", "great job by the staff",
        "bahut accha kaam, jaldi solve hua", "impressed with the fast action", "staff came immediately, thanks a lot"],
    4: ["issue resolved, good response", "thanks, problem fixed", "satisfied with the action taken", "good, but could be faster",
        "problem solved, thank you"],
    3: ["issue resolved but took long time", "ok service", "average response", "partially solved", "someone came but late"],
    2: ["very late response", "problem not fully solved", "staff came after hours, not happy", "slow action, disappointed",
        "complaint closed without solving"],
    1: ["nobody came, worst service", "complaint closed without any action, pathetic", "useless system, no response at all",
        "koi nahi aaya, bekar service", "totally unsatisfied, waste of time", "fake closure of complaint, shameful"],
}


def _feedback(rating):
    # People with the same rating word their feedback differently, and
    # neighbouring ratings share vocabulary, so sentiment is not trivial.
    r = rng.random()
    bank = rating if r < 0.6 else int(np.clip(rating + rng.choice([-1, 1]), 1, 5)) if r < 0.9 else int(rng.integers(1, 6))
    t = str(rng.choice(FB[bank]))
    if rng.random() < 0.2:
        t += ", " + str(rng.choice(FB[rating]))
    return add_typos(t, 0.1) if rng.random() < 0.25 else t


def main():
    df, trains = simulate()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    trains.to_csv(OUT.parent / "train_master.csv", index=False)
    print(f"{len(df)} complaints, {df['incident_id'].nunique()} incidents, {len(trains)} trains -> {OUT}")
    print(df["category"].value_counts().to_string())


if __name__ == "__main__":
    main()
