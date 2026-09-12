import csv
import json
import random
from datetime import datetime, timedelta

# ==========================================
# 1. CONSTANTS & MASTER DATABASES
# ==========================================

CAR_MAKES_MODELS = [
    ("Hyundai", "Creta"), ("Hyundai", "i20"), ("Tata", "Nexon"),
    ("Tata", "Harrier"), ("Maruti", "Swift"), ("Maruti", "Brezza"),
    ("Mahindra", "Thar"), ("Mahindra", "XUV700"), ("Toyota", "Fortuner")
]

CAR_COLORS = ["White", "Black", "Silver", "Grey", "Red", "Blue"]
STATE_RTO_CODES = ["MH-04", "MH-02", "MH-12", "MH-46", "MH-03"]

DISTRICTS = ["Thane", "Panvel", "Belapur", "Seawoods", "Khandeshwar", "Kharghar", "Airoli", "Kalyan", "Nerul"]
COORDINATED_DISTRICTS = ["Airoli", "Kalyan", "Nerul"]

MALE_NAMES = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Rohan", "Rahul", "Vikram", "Suresh"]
FEMALE_NAMES = ["Diya", "Saanvi", "Ananya", "Aadhya", "Anika", "Riya", "Pooja", "Neha", "Priya"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Malhotra", "Mehta", "Patel", "Deshmukh", "Singh", "Kumar"]

MALE_PLANNED_NAMES = ["Mogambo", "Shakaal", "Kancha", "Gabbar", "Don", "Teja"]
FEMALE_PLANNED_NAMES = ["Komolika", "Madame", "Bindoo"]
LAST_PLANNED_NAMES = ["The Don", "Dang", "Cheena", "Singh", "Gogo", "Pathan"]

PROPERTY_TYPES = ["Mobile Phone", "Gold Jewelry", "Motor Vehicle", "Cash", "Laptops", "Electronic Gadgets"]
DELAY_REASONS = ["Informant was admitted to hospital", "Attempted out-of-court mediation", "Threatened by accused", "Fear of social stigma", "None / Immediate Reporting"]

TOLL_PLAZAS = [
    {"id": "TP-0102", "name": "Vashi Toll Plaza", "corridor": "Mumbai-Panvel"},
    {"id": "TP-0105", "name": "Khalapur Toll Plaza", "corridor": "Mumbai-Pune Expressway"},
    {"id": "TP-0108", "name": "Urse Toll Plaza", "corridor": "Mumbai-Pune Expressway"},
    {"id": "TP-0210", "name": "Khed Toll Plaza", "corridor": "NH-48 (Pune-Satara)"}
]

ANPR_CAMERAS = [
    {"id": "ANPR-MH04-VSH", "loc": "Vashi Bridge, Mumbai", "coords": "19.0596 N, 72.9011 E"},
    {"id": "ANPR-MPE-KHL", "loc": "Khalapur Km 42", "coords": "18.8021 N, 73.2104 E"},
    {"id": "ANPR-MPE-URS", "loc": "Urse Toll Km 84", "coords": "18.7112 N, 73.6102 E"},
    {"id": "ANPR-NH48-KHD", "loc": "Khed Plaza Km 120", "coords": "18.3512 N, 73.8901 E"}
]

BNS_CRIME_DATABASE = {
    "Rape": {"bns": "BNS Section 63", "category": "Women/Children", "severity": (3, 7)},
    "Sexual Harassment": {"bns": "BNS Section 75", "category": "Women/Children", "severity": (1, 3)},
    "Stalking": {"bns": "BNS Section 78", "category": "Women/Children", "severity": (1, 4)},
    "Dowry Death": {"bns": "BNS Section 80", "category": "Women/Children", "severity": (4, 10)},
    "Kidnapping of Minor": {"bns": "BNS Section 137", "category": "Women/Children", "severity": (1, 3)},
    "Child Trafficking": {"bns": "BNS Section 143", "category": "Women/Children", "severity": (5, 14)},
    "Murder": {"bns": "BNS Section 103(1)", "category": "Violent", "severity": (5, 12)},
    "Attempt to Murder": {"bns": "BNS Section 109", "category": "Violent", "severity": (2, 6)},
    "Grievous Hurt": {"bns": "BNS Section 117", "category": "Violent", "severity": (1, 5)},
    "Acid Attack": {"bns": "BNS Section 124", "category": "Violent", "severity": (2, 7)},
    "Mob Lynching": {"bns": "BNS Section 103(2)", "category": "Violent", "severity": (3, 9)},
    "Theft": {"bns": "BNS Section 303", "category": "Property", "severity": (1, 2)},
    "Snatching": {"bns": "BNS Section 304", "category": "Property", "severity": (1, 3)},
    "Robbery": {"bns": "BNS Section 309", "category": "Property", "severity": (1, 4)},
    "Dacoity": {"bns": "BNS Section 310", "category": "Property", "severity": (2, 6)},
    "Extortion": {"bns": "BNS Section 308", "category": "Property", "severity": (3, 7)},
    "Criminal Breach of Trust": {"bns": "BNS Section 316", "category": "Financial", "severity": (2, 8)},
    "Cyber Fraud": {"bns": "BNS Section 318(4)", "category": "Cyber", "severity": (2, 8)},
    "Organized Crime Syndicate": {"bns": "BNS Section 111", "category": "Organized", "severity": (7, 15)},
    "Petty Organized Crime": {"bns": "BNS Section 112", "category": "Organized", "severity": (3, 8)},
    "Terrorist Act": {"bns": "BNS Section 113", "category": "State/Terror", "severity": (10, 30)}
}

# ==========================================
# 2. HELPER UTILITIES
# ==========================================

def generate_number_plate():
    rto = random.choice(STATE_RTO_CODES)
    letters = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=2))
    digits = f"{random.randint(1000, 9999)}"
    return f"{rto}-{letters}-{digits}"

def generate_phone_number():
    return f"9{random.randint(100000009, 999999999)}"

def sanitize_phone(phone_str):
    if not phone_str or str(phone_str).strip().upper() in ["N/A", "NAN", "NONE", ""]:
        return generate_phone_number()
    clean = "".join(filter(str.isdigit, str(phone_str)))
    return clean[-10:] if len(clean) >= 10 else generate_phone_number()

def generate_vehicle_details(prob_known=1.0):
    if random.random() > prob_known:
        return []

    num_vehicles = random.choices([1, 2], weights=[0.85, 0.15], k=1)[0]
    vehicles = []
    
    for _ in range(num_vehicles):
        make, model = random.choice(CAR_MAKES_MODELS)
        color = random.choice(CAR_COLORS)
        vehicles.append({
            "number_plate": generate_number_plate(),
            "color": color,
            "make": make,
            "model": model,
            "full_description": f"{color} {make} {model}"
        })
    return vehicles

def generate_person(role="general", connectivity="Unplaned", fixed_age=None, fixed_gender=None, vehicle_prob=1.0):
    gender = fixed_gender if fixed_gender else random.choice(['Male', 'Female'])
    age = fixed_age if fixed_age is not None else random.randint(18, 75)
    
    if role == "accused":
        first_name = random.choice(MALE_PLANNED_NAMES if gender == 'Male' else FEMALE_PLANNED_NAMES)
        last_name = random.choice(LAST_PLANNED_NAMES)
    else:
        first_name = random.choice(MALE_NAMES if gender == 'Male' else FEMALE_NAMES)
        last_name = random.choice(LAST_NAMES)

    return {
        "name": f"{first_name} {last_name}",
        "age": age,
        "gender": gender,
        "father_husband_name": f"{random.choice(MALE_NAMES)} {last_name}",
        "address": random.choice(COORDINATED_DISTRICTS if connectivity == "Planed" else DISTRICTS),
        "contact": generate_phone_number(),
        "national_id": "[Aadhaar Redacted]",
        "passport_no": f"Z{random.randint(1000000, 9999999)}",
        "occupation": random.choice(["Business", "Service", "Student", "Unemployed", "Self-Employed"]),
        "vehicles": generate_vehicle_details(prob_known=vehicle_prob)
    }

def classify_vulnerability(age, gender, crime):
    if age < 18 or crime in ["Kidnapping of Minor", "Child Trafficking"]:
        return "Crime Against Child"
    elif gender == "Female" or crime in ["Rape", "Sexual Harassment", "Stalking", "Dowry Death"]:
        return "Crime Against Women"
    elif age >= 60:
        return "Crime Against Elderly"
    else:
        return "General Offense"

def save_csv(filename, data):
    if not data:
        return
    with open(filename, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)

# ==========================================
# 3. FIR GENERATION MODULE
# ==========================================

def generate_fir_dataset(count=20):
    dataset = []
    for case_idx in range(1, count + 1):
        district = random.choice(DISTRICTS)
        police_station = f"{district} PS"
        
        case_type = random.choice(list(BNS_CRIME_DATABASE.keys()))
        crime_meta = BNS_CRIME_DATABASE[case_type]
        connectivity = random.choice(["Planed", "Unplaned"])

        if crime_meta["category"] == "Women/Children":
            if case_type in ["Kidnapping of Minor", "Child Trafficking"]:
                v_age, v_gender = random.randint(3, 17), random.choice(["Male", "Female"])
            else:
                v_age, v_gender = random.randint(18, 55), "Female"
        else:
            v_age, v_gender = random.randint(18, 75), random.choice(["Male", "Female"])

        informant = generate_person("informant", connectivity, vehicle_prob=0.7)
        victim = generate_person("victim", connectivity, fixed_age=v_age, fixed_gender=v_gender, vehicle_prob=0.8)
        
        accused_known = random.choice([True, False])
        acc_vehicle_prob = 0.90 if accused_known else 0.35
        accused = generate_person("accused", connectivity, vehicle_prob=acc_vehicle_prob)

        r_start = datetime.strptime("01-08-2026", "%d-%m-%Y")
        r_end = datetime.strptime("31-08-2026", "%d-%m-%Y")
        report_dt = r_start + timedelta(days=random.randint(0, (r_end - r_start).days))

        min_n, max_n = crime_meta["severity"]
        if connectivity == "Planed":
            min_n += 2
            max_n += 3
        
        n_days_offset = random.randint(min_n, max_n)
        occurrence_dt = report_dt - timedelta(days=n_days_offset)
        prop_val = random.randint(5000, 500000) if crime_meta["category"] in ["Property", "Financial", "Cyber"] else 0

        row = {
            "District": district,
            "Police_Station": police_station,
            "State_UT": "Maharashtra",
            "FIR_No": f"FIR/2026/{case_idx:04d}",
            "Year": 2026,
            "Date_Time_of_FIR": f"{report_dt.strftime('%Y-%m-%d')} {random.randint(10,23)}:00",
            "Acts_Sections": crime_meta["bns"],
            "Case_Type": case_type,
            "Connectivity_Type": connectivity,
            "Vulnerability_Category": classify_vulnerability(victim["age"], victim["gender"], case_type),
            "Days_Offset_N": n_days_offset,
            "Day_of_Occurrence": occurrence_dt.strftime("%A"),
            "Occurrence_Date_Range": f"{occurrence_dt.strftime('%Y-%m-%d')} to {report_dt.strftime('%Y-%m-%d')}",
            "Time_Period_Shift": random.choice(["Morning Shift", "Evening Shift", "Night Shift"]),
            "GD_Reference_Entry_No": f"GD-{random.randint(100, 999)}/2026",
            "Type_of_Information": random.choice(["Written", "Oral"]),
            "Direction_Distance_from_PS": f"{random.randint(1, 15)} km {random.choice(['North', 'South', 'East', 'West'])}",
            "Beat_No": f"Beat-{random.randint(1, 12)}",
            "Place_of_Occurrence": random.choice(COORDINATED_DISTRICTS if connectivity == "Planed" else DISTRICTS),
            "Outside_Jurisdiction_PS": "N/A",
            "Informant_Name": informant["name"],
            "Informant_Father_Husband": informant["father_husband_name"],
            "Informant_Age": informant["age"],
            "Informant_Gender": informant["gender"],
            "Informant_Nationality": "Indian",
            "Informant_Passport_No": informant["passport_no"],
            "Informant_Aadhaar": informant["national_id"],
            "Informant_Occupation": informant["occupation"],
            "Informant_Address": informant["address"],
            "Informant_Contact": informant["contact"],
            "Informant_Vehicles": "; ".join([f"{v['number_plate']} ({v['color']} {v['make']} {v['model']})" for v in informant["vehicles"]]) if informant["vehicles"] else "None",
            "Victim_Name": victim["name"],
            "Victim_Age": victim["age"],
            "Victim_Gender": victim["gender"],
            "Victim_Contact": victim["contact"],
            "Victim_Aadhaar": victim["national_id"],
            "Victim_Vehicles": "; ".join([f"{v['number_plate']} ({v['color']} {v['make']} {v['model']})" for v in victim["vehicles"]]) if victim["vehicles"] else "None",
            "Accused_Status": "Known" if accused_known else "Unknown",
            "Number_of_Accused": 1 if accused_known else random.randint(1, 4),
            "Accused_Name_Alias": accused["name"],
            "Accused_Contact": accused["contact"],
            "Accused_Address": accused["address"],
            "Accused_Build": random.choice(["Slim", "Medium", "Athletic", "Heavy"]),
            "Accused_Height_cm": random.randint(155, 185),
            "Accused_Complexion": random.choice(["Fair", "Wheatish", "Dark"]),
            "Accused_Distinctive_Marks": random.choice(["Scar on left cheek", "Tattoo on right forearm", "Mole on neck", "None"]),
            "Accused_Vehicles": "; ".join([f"{v['number_plate']} ({v['color']} {v['make']} {v['model']})" for v in accused["vehicles"]]) if accused["vehicles"] else "None",
            "Accused_Vehicle_Identified_Probability": 1.0 if accused_known else (0.35 if accused["vehicles"] else 0.0),
            "Reasons_for_Delay": random.choice(DELAY_REASONS) if n_days_offset > 2 else "None / Immediate Reporting",
            "Inquest_UD_Case_No": f"UD-{random.randint(100,999)}/2026" if crime_meta["category"] == "Violent" else "N/A",
            "Property_Category_Type": random.choice(PROPERTY_TYPES) if prop_val > 0 else "N/A",
            "Property_Description_Serial_No": f"Serial/IMEI-{random.randint(100000, 999999)}" if prop_val > 0 else "N/A",
            "Total_Property_Value_INR": prop_val,
            "FIR_Narrative_Statement": f"On {occurrence_dt.strftime('%Y-%m-%d')}, an offense of {case_type} was reported at {police_station} by {informant['name']}. Legal proceedings initiated under {crime_meta['bns']}.",
            "Action_Taken": "Registered & Took Up Investigation",
            "Investigating_Officer_Name": f"Inspector {random.choice(MALE_NAMES)} {random.choice(LAST_NAMES)}",
            "IO_Badge_No": f"MH-POL-{random.randint(1000, 9999)}",
            "Complainant_Sign_Acknowledged": "Yes",
            "Free_Copy_Delivered": "Yes",
            "Date_Time_Dispatch_to_Court": f"{report_dt.strftime('%Y-%m-%d')} 18:00"
        }
        dataset.append(row)

    save_csv("complete_fir_dataset.csv", dataset)
    return dataset

# ==========================================
# 4. TELECOM & CDR GENERATION MODULE
# ==========================================

TSPS = ["Reliance Jio Infocomm Ltd", "Bharti Airtel Ltd", "Vodafone Idea Ltd", "BSNL"]
CIRCLES = ["Maharashtra & Goa", "Mumbai", "Delhi", "Gujarat"]
TOWERS = ["Dadar West, Mumbai", "Andheri East, Mumbai", "Lower Parel, Mumbai", "Thane West, Thane", "Vashi, Navi Mumbai", "Airoli, Navi Mumbai", "Kharghar, Navi Mumbai"]
CELL_IDS = ["404-45-1021-4321", "404-45-1021-4322", "404-45-1021-4325", "404-45-1022-1001"]
TOR_PROXIES = ["185.220.101.4", "185.220.101.5", "103.211.54.12"]
CLEAN_IPS = ["49.36.12.84", "106.210.34.12", "157.33.12.90", "103.211.54.99"]

def gen_imei(): return f"86{random.randint(1000000000003, 9999999999999)}"
def gen_imsi(): return f"40445{random.randint(1000000020, 9999999999)}"

def generate_telecom_data(fir_cases):
    sdr_records = []
    cdr_records = []
    ipdr_records = []
    case_suspicious_map = {}

    for case in fir_cases:
        case_id = case["FIR_No"]
        accused_phone = sanitize_phone(case.get("Accused_Contact"))
        victim_phone = sanitize_phone(case.get("Victim_Contact"))
        informant_phone = sanitize_phone(case.get("Informant_Contact"))

        entities = [
            {"role": "ACCUSED", "phone": accused_phone, "name": case.get("Accused_Name_Alias")},
            {"role": "VICTIM", "phone": victim_phone, "name": case.get("Victim_Name")},
            {"role": "INFORMANT", "phone": informant_phone, "name": case.get("Informant_Name")}
        ]

        flagged_role = random.choices(["ACCUSED", "VICTIM", "INFORMANT"], weights=[0.5, 0.3, 0.2], k=1)[0]
        case_suspicious_map[case_id] = {
            "flagged_role": flagged_role,
            "accused_phone": accused_phone,
            "victim_phone": victim_phone,
            "informant_phone": informant_phone
        }

        telecom_map = {}
        for ent in entities:
            imei = gen_imei()
            imsi = gen_imsi()
            telecom_map[ent["role"]] = {"phone": ent["phone"], "imei": imei, "imsi": imsi}

            sdr_records.append({
                "Case_ID": case_id,
                "Mobile Number": ent["phone"],
                "Subscriber Name": ent["name"],
                "Father/Husband Name": f"Suresh {ent['name'].split()[-1]}",
                "Local Address": case.get("Place_of_Occurrence", "Mumbai, MH"),
                "Permanent Address": "Maharashtra, India",
                "Proof of Identity (PoI)": "Aadhaar: [Aadhaar Redacted]",
                "Proof of Address (PoA)": f"Electricity Bill: {random.randint(10000000, 99999999)}",
                "Activation Date & Time": "14-MAR-2022 11:42:15 IST",
                "Service Provider / Circle": f"{random.choice(TSPS)} / {random.choice(CIRCLES)}",
                "IMSI Number": imsi,
                "SIM Card ID (ICCID)": f"89918520000{random.randint(100000, 999999)}F",
                "Alternate Contact No.": informant_phone if ent["role"] == flagged_role else generate_phone_number()
            })

        # Map each phone number back to its role so the correct IMEI/IMSI
        # (i.e. the calling party's actual device) is stamped on each record.
        phone_to_role = {
            victim_phone: "VICTIM",
            informant_phone: "INFORMANT",
            accused_phone: "ACCUSED"
        }

        base_time = datetime.strptime("04/09/2026 09:00", "%d/%m/%Y %H:%M")
        for i in range(49):
            party_a = random.choice([victim_phone, informant_phone, accused_phone])
            party_b = generate_phone_number()
            caller_device = telecom_map[phone_to_role[party_a]]
            cdr_records.append({
                "Case_ID": case_id,
                "Calling Number (A-Party)": party_a,
                "Called Number (B-Party)": party_b,
                "Call Date & Time": (base_time + timedelta(minutes=i * 15)).strftime("%d/%m/%Y %H:%M"),
                "Type": random.choice(["MOC", "MTC"]),
                "Duration (s)": random.randint(10, 300),
                "IMEI": caller_device["imei"],
                "IMSI Number": caller_device["imsi"],
                "Start Cell ID": random.choice(CELL_IDS),
                "End Cell ID": random.choice(CELL_IDS),
                "First Tower Location": random.choice(TOWERS),
                "Last Tower Location": random.choice(TOWERS)
            })

        if flagged_role == "VICTIM":
            suspicious_log = {
                "Case_ID": case_id,
                "Calling Number (A-Party)": victim_phone,
                "Called Number (B-Party)": accused_phone,
                "Call Date & Time": "04/09/2026 02:15",
                "Type": "MOC",
                "Duration (s)": 3,
                "IMEI": telecom_map["VICTIM"]["imei"],
                "IMSI Number": telecom_map["VICTIM"]["imsi"],
                "Start Cell ID": "404-45-1021-4322",
                "End Cell ID": "404-45-1021-4325",
                "First Tower Location": "Dadar West, Mumbai",
                "Last Tower Location": "Andheri East, Mumbai"
            }
        elif flagged_role == "INFORMANT":
            suspicious_log = {
                "Case_ID": case_id,
                "Calling Number (A-Party)": informant_phone,
                "Called Number (B-Party)": accused_phone,
                "Call Date & Time": "04/09/2026 03:10",
                "Type": "MOC",
                "Duration (s)": 120,
                "IMEI": telecom_map["INFORMANT"]["imei"],
                "IMSI Number": telecom_map["INFORMANT"]["imsi"],
                "Start Cell ID": "404-45-1021-4321",
                "End Cell ID": "404-45-1021-4321",
                "First Tower Location": "Airoli, Navi Mumbai",
                "Last Tower Location": "Airoli, Navi Mumbai"
            }
        else:
            suspicious_log = {
                "Case_ID": case_id,
                "Calling Number (A-Party)": accused_phone,
                "Called Number (B-Party)": victim_phone,
                "Call Date & Time": "04/09/2026 01:30",
                "Type": "MOC",
                "Duration (s)": 4,
                "IMEI": telecom_map["ACCUSED"]["imei"],
                "IMSI Number": telecom_map["ACCUSED"]["imsi"],
                "Start Cell ID": "404-45-1021-4325",
                "End Cell ID": "404-45-1021-4325",
                "First Tower Location": "Kharghar, Navi Mumbai",
                "Last Tower Location": "Kharghar, Navi Mumbai"
            }
        cdr_records.append(suspicious_log)

        for i in range(30):
            pub_ip = random.choice(TOR_PROXIES) if (flagged_role in ["VICTIM", "INFORMANT"] and i == 29) else random.choice(CLEAN_IPS)
            ipdr_records.append({
                "Case_ID": case_id,
                "Session Start Time": (base_time + timedelta(minutes=i * 10)).strftime("%d/%m/%Y %H:%M:%S"),
                "Session End Time": (base_time + timedelta(minutes=i * 10 + 5)).strftime("%d/%m/%Y %H:%M:%S"),
                "Allocated Private IP": f"10.240.12.{random.randint(1, 254)}",
                "Private Port": random.randint(49152, 65535),
                "Source Public IP": pub_ip,
                "Public Port": random.randint(1024, 5000),
                "Destination IP": "157.240.22.60",
                "Protocol": "TCP",
                "Destination Port": 443,
                "Volume In (Bytes)": random.randint(100000, 5000000),
                "Volume Out (Bytes)": 8450200 if pub_ip in TOR_PROXIES else 1240500,
                "RAT Type": "4G/LTE"
            })

    save_csv("Subscriber_Detail_Records.csv", sdr_records)
    save_csv("Call_Recording.csv", cdr_records)
    save_csv("IP_Detail_Records.csv", ipdr_records)

    return sdr_records, cdr_records, ipdr_records, case_suspicious_map

# ==========================================
# 5. VEHICLE INTELLIGENCE & MULTI-RULE ANOMALY ENGINE
# ==========================================

def parse_vehicle_string(vehicle_str):
    if not vehicle_str or str(vehicle_str).strip() in ("", "None", "N/A", "NaN"):
        return None
    try:
        first_veh = vehicle_str.split("; ")[0].strip()
        parts = first_veh.split(" (", 1)
        plate = parts[0].strip() if parts[0].strip() else generate_number_plate()

        details = parts[1].rstrip(")").strip() if len(parts) > 1 and parts[1].strip() else "White Hyundai Creta"
        detail_tokens = details.split(" ", 1)
        color = detail_tokens[0] if detail_tokens and detail_tokens[0] else "White"
        make_model = detail_tokens[1] if len(detail_tokens) > 1 and detail_tokens[1] else "Hyundai Creta"

        return {"plate": plate, "color": color, "make_model": make_model}
    except (IndexError, AttributeError):
        # Malformed input (unexpected format) - fall back to a safe default
        # instead of crashing the whole pipeline mid-run.
        return {"plate": generate_number_plate(), "color": "White", "make_model": "Hyundai Creta"}

def generate_vehicle_intelligence_and_detect_anomalies(fir_cases, case_suspicious_map):
    vahan_db, sarathi_db, fastag_logs, anpr_logs, master_vehicle_records = [], [], [], [], []
    anomalies_detected = []

    for case in fir_cases:
        case_id = case["FIR_No"]
        meta = case_suspicious_map[case_id]
        flagged_role = meta["flagged_role"]

        roles = [
            ("INFORMANT", case["Informant_Name"], case["Informant_Contact"], case.get("Informant_Vehicles")),
            ("VICTIM", case["Victim_Name"], case["Victim_Contact"], case.get("Victim_Vehicles")),
            ("ACCUSED", case["Accused_Name_Alias"], case["Accused_Contact"], case.get("Accused_Vehicles"))
        ]

        for role_name, person_name, contact, veh_str in roles:
            phone_num = sanitize_phone(contact)
            dl_num = f"MH-042022{random.randint(1000000, 9999999)}"
            is_suspect = (role_name == flagged_role)

            sarathi_phone = phone_num if not (is_suspect and random.random() < 0.3) else generate_phone_number()

            sarathi_entry = {
                "Case_ID": case_id,
                "Role": role_name,
                "Driving License No": dl_num,
                "License Holder": person_name,
                "Father/Husband Name": f"Suresh {person_name.split()[-1]}",
                "Issuing RTO": "MH-04 (Thane RTO)",
                # TODO: hardcoded for every person incl. those with no vehicle -
                # low impact, left as-is unless you want it tied to actual ownership.
                "Class of Vehicle": "LMV, MCWG",
                "Linked Mobile": sarathi_phone,
                "License Status": "ACTIVE"
            }
            sarathi_db.append(sarathi_entry)

            veh_details = parse_vehicle_string(veh_str)

            if not veh_details:
                master_vehicle_records.append({
                    "Case_ID": case_id, "Person_Role": role_name, "Person_Name": person_name,
                    "Has_Vehicle": "NO", "Plate": "N/A", "FASTag_ID": "N/A", "VAHAN_Status": "N/A"
                })
                continue

            real_plate = veh_details["plate"]
            fastag_id = f"TAG34161FA{random.randint(100000, 999999)}"
            vahan_status = "ACTIVE (Flagged for Tracking)" if is_suspect else "ACTIVE"

            vahan_entry = {
                "Case_ID": case_id,
                "Registration Number": real_plate,
                "Owner Name": person_name,
                "Vehicle Class": "Motor Car (LMV)",
                "Maker / Model": veh_details["make_model"],
                "Chassis Number": f"MA3A{random.randint(1000000000, 9999999999)}",
                "Engine Number": f"ENG{random.randint(1000000, 9999999)}",
                "Fuel Type": "PETROL/BS-VI",
                "Linked Mobile": phone_num,
                "Vehicle Status": vahan_status
            }
            vahan_db.append(vahan_entry)

            master_vehicle_records.append({
                "Case_ID": case_id, "Person_Role": role_name, "Person_Name": person_name,
                "Has_Vehicle": "YES", "Plate": real_plate, "FASTag_ID": fastag_id, "VAHAN_Status": vahan_status
            })

            if sarathi_phone != phone_num:
                anomalies_detected.append({
                    "Case_ID": case_id,
                    "Rule_Violated": "RULE 4: SARATHI / VAHAN MOBILE DISCREPANCY",
                    "Severity": "MEDIUM",
                    "Person": f"{person_name} ({role_name})",
                    "Details": f"SARATHI Registered Mobile ({sarathi_phone}) does not match VAHAN Registered Mobile ({phone_num}). Potential Synthetic Identity / Proxy Ownership."
                })

            num_logs = random.randint(2, 4)
            base_time = datetime.strptime("2026-09-08 08:00:00", "%Y-%m-%d %H:%M:%S")

            for log_idx in range(num_logs):
                log_time = (base_time + timedelta(minutes=log_idx * 45)).strftime("%Y-%m-%d %H:%M:%S")
                plaza = TOLL_PLAZAS[log_idx % len(TOLL_PLAZAS)]
                camera = ANPR_CAMERAS[log_idx % len(ANPR_CAMERAS)]

                captured_plate = real_plate
                anomaly_type = None

                if is_suspect and log_idx == (num_logs - 1):
                    anomaly_choice = random.choice(["RULE_1_CLONED_PLATE", "RULE_2_GEO_ALIBI"])
                    
                    if anomaly_choice == "RULE_1_CLONED_PLATE":
                        captured_plate = generate_number_plate()
                        anomaly_type = "RULE 1: FASTAG / ANPR PLATE MISMATCH (CLONED PLATE)"
                        anomalies_detected.append({
                            "Case_ID": case_id,
                            "Rule_Violated": "RULE 1: FASTag Tag ID vs. ANPR OCR Mismatch",
                            "Severity": "CRITICAL",
                            "Person": f"{person_name} ({role_name})",
                            "Details": f"FASTag Tag ({fastag_id}) registered to plate {real_plate} passed {plaza['name']}, but ANPR OCR scanned plate {captured_plate}. Cloned plate or illicit tag transfer detected."
                        })
                    else:
                        anomaly_type = "RULE 2: CDR SUSPECT GEO-SPATIAL ALIBI BREACH"
                        anomalies_detected.append({
                            "Case_ID": case_id,
                            "Rule_Violated": "RULE 2: Geo-Spatial Alibi Discrepancy",
                            "Severity": "HIGH",
                            "Person": f"{person_name} ({role_name})",
                            "Details": f"Suspect vehicle ({real_plate}) scanned at {camera['loc']} at {log_time}, contradicting suspect's CDR tower alibi location."
                        })

                fastag_logs.append({
                    "Case_ID": case_id, "Person_Role": role_name, "Timestamp (IST)": log_time,
                    "Toll Plaza ID & Location": f"{plaza['id']} / {plaza['name']}", "Corridor": plaza["corridor"],
                    "Vehicle Registration": real_plate, "FASTag Tag ID": fastag_id, "Toll Fee (INR)": 110,
                    "ANPR Cross-Match": "MISMATCH" if captured_plate != real_plate else "MATCH",
                    "Txn Status": "FLAG_ALERT" if anomaly_type else "SUCCESS"
                })

                anpr_logs.append({
                    "Case_ID": case_id, "Person_Role": role_name, "Detection Time": log_time,
                    "Camera ID & Location": f"{camera['id']} / {camera['loc']}", "GPS Coordinates": camera["coords"],
                    "Captured Plate": captured_plate, "OCR Confidence": f"{random.uniform(95.0, 99.9):.2f}%",
                    "Vehicle Color & Class": f"{veh_details['color']} {veh_details['make_model']}",
                    "VAHAN Match": "MISMATCH_SUSPECT" if captured_plate != real_plate else "MATCH",
                    "Investigation Flag": anomaly_type if anomaly_type else "PASS"
                })

    save_csv("Vehicle_Summary.csv", master_vehicle_records)
    save_csv("VAHAN_Database.csv", vahan_db)
    save_csv("SARATHI_Database.csv", sarathi_db)
    save_csv("FASTag_Toll_Logs.csv", fastag_logs)
    save_csv("ANPR_Camera_Feeds.csv", anpr_logs)

    return vahan_db, sarathi_db, fastag_logs, anpr_logs, master_vehicle_records, anomalies_detected

# ==========================================
# 6. FINANCIAL & CRYPTOCURRENCY INTELLIGENCE MODULE
# ==========================================
# Depth of financial forensics generated per case mirrors how an actual
# investigating agency scopes its financial angle: organized / financial /
# cyber crime gets full banking + crypto + shell-company forensics pulled;
# planned-but-non-financial cases get a partial trail; routine unplanned
# offenses rarely get more than a light bank check, and often nothing at all.

BANKS_IFSC = [
    ("State Bank of India", "SBIN0001234"), ("HDFC Bank", "HDFC0000060"),
    ("ICICI Bank", "ICIC0000104"), ("Punjab National Bank", "PUNB0001122"),
    ("Axis Bank", "UTIB0000987"), ("Bank of Baroda", "BARB0DBSURT")
]
UPI_HANDLES = ["okaxis", "ybl", "paytm", "okicici", "oksbi", "ibl"]
PAYMENT_GATEWAYS = ["Razorpay", "Paytm", "PhonePe", "Cashfree", "BillDesk"]
MERCHANT_NAMES = ["CloudRetail", "FastPay Tech", "QuickDigital", "UrbanMart Traders", "ZenithTrade Co"]

BLOCKCHAINS = [("Ethereum (ERC-20)", "USDT"), ("TRON (TRC-20)", "USDT"), ("Bitcoin", "BTC"), ("Polygon (POS)", "USDT")]
CRYPTO_EXCHANGES = [
    ("WazirX", "FIU-IND-VDA-0004"), ("CoinDCX", "FIU-IND-VDA-0011"),
    ("ZebPay", "FIU-IND-VDA-0021"), ("Bitbns", "FIU-IND-VDA-0037")
]

# Deliberately reused across multiple shell companies - a shared registered
# address across unrelated entities is itself a standard shell-company red flag.
SHELL_REGISTERED_ADDRESSES = [
    "Office 3B, Express Towers, Nariman Point, Mumbai",
    "Shop 12, Chawl No 4, Dharavi, Mumbai",
    "Unit 402, Cyber Gate, Andheri East, Mumbai"
]

COMPANY_PREFIXES = ["Apex", "Zenith", "Vanguard", "Quantum", "Novatech", "Shreeji", "Blue Ocean", "Sterling"]
COMPANY_SUFFIXES = ["Trading Pvt Ltd", "Logistics Pvt Ltd", "Infra-Ventures Pvt Ltd", "Digital Solutions Pvt Ltd", "Global Exports Pvt Ltd"]
GST_COMMODITIES = [("7208", "Flat Iron/Steel"), ("8517", "Mobile Phones/Telecom Equip"), ("7113", "Gold Jewelry"), ("2710", "Petroleum Products")]
CREDIT_INSTITUTIONS = ["State Bank of India", "Punjab National Bank", "HDFC Bank", "Bank of Baroda"]
AUDITORS = ["CA M. K. Gupta (MNo 045912)", "CA R. S. Iyer (MNo 067823)", "CA P. N. Deshpande (MNo 091234)"]


def generate_vpa(name):
    handle = "".join(ch for ch in name.lower() if ch.isalnum())[:10] or "user"
    return f"{handle}{random.randint(10, 99)}@{random.choice(UPI_HANDLES)}"

def generate_account_number():
    return f"{random.randint(100000000000, 999999999999)}"

def generate_utr():
    return f"UTR{random.randint(100000000000, 999999999999)}"

def generate_gstin():
    state_code = random.choice(["27", "07", "24", "29"])
    letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5))
    return f"{state_code}{letters}{random.randint(1000, 9999)}A1Z{random.randint(1, 9)}"

def generate_cin():
    return f"U{random.randint(10000, 99999)}MH{random.randint(2015, 2023)}PTC{random.randint(100000, 999999)}"

def generate_din():
    return f"{random.randint(1000000, 9999999)}"

def generate_pan(is_company=False):
    letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5))
    return f"{letters}{random.randint(1000, 9999)}{'C' if is_company else 'P'}"

def generate_wallet_address(chain):
    if "Bitcoin" in chain:
        return "bc1q" + "".join(random.choices("abcdefghjklmnpqrstuvwxyz0123456789", k=38))
    return "0x" + "".join(random.choices("abcdef0123456789", k=40))

def generate_txhash():
    return "0x" + "".join(random.choices("abcdef0123456789", k=64))

def generate_company_name():
    return f"{random.choice(COMPANY_PREFIXES)} {random.choice(COMPANY_SUFFIXES)}"


def determine_financial_tier(case):
    """
    NONE     - no financial trail pulled (most routine/unplanned cases)
    BASIC    - a handful of plain bank + UPI records, rarely any red flag
    MODERATE - adds merchant/gateway logs, occasional structuring/mule flag
    COMPLEX  - full banking + crypto + shell-company + GST + ITR + CIBIL trail,
               reserved mostly for organized/financial/cyber & planned cases
    """
    category = BNS_CRIME_DATABASE[case["Case_Type"]]["category"]
    planned = case["Connectivity_Type"] == "Planed"

    if category in ["Organized", "Financial", "Cyber"] and planned:
        weights = [0.05, 0.10, 0.20, 0.65]
    elif category in ["Organized", "Financial", "Cyber"]:
        weights = [0.15, 0.25, 0.35, 0.25]
    elif planned:
        weights = [0.35, 0.30, 0.25, 0.10]
    else:
        weights = [0.75, 0.20, 0.05, 0.00]

    return random.choices(["NONE", "BASIC", "MODERATE", "COMPLEX"], weights=weights, k=1)[0]


def select_financial_suspect(case, case_suspicious_map):
    """
    Reuses the person already flagged by CDR/Vehicle intelligence as the
    financial suspect 70% of the time, keeping one coherent suspect across
    every module. The remaining 30% hands the financial angle to a
    *different* role (e.g. a money-mule whose account moves the funds even
    though someone else made the incriminating calls) - a realistic pattern
    in genuine layering schemes, and useful for cross-checking exercises.
    """
    case_id = case["FIR_No"]
    cdr_role = case_suspicious_map[case_id]["flagged_role"]
    role = cdr_role if random.random() < 0.70 else random.choice(
        [r for r in ["ACCUSED", "VICTIM", "INFORMANT"] if r != cdr_role]
    )
    name_field = {"ACCUSED": "Accused_Name_Alias", "VICTIM": "Victim_Name", "INFORMANT": "Informant_Name"}[role]
    phone_field = {"ACCUSED": "Accused_Contact", "VICTIM": "Victim_Contact", "INFORMANT": "Informant_Contact"}[role]
    name = case.get(name_field, "Unknown")
    phone = sanitize_phone(case.get(phone_field))
    return role, name, phone


def generate_financial_intelligence(fir_cases, case_suspicious_map):
    bank_records, upi_records, merchant_records = [], [], []
    crypto_onchain, crypto_kyc, crypto_onoff = [], [], []
    itr_records, gst_records, cibil_records, roc_records = [], [], [], []
    financial_summary = []
    financial_anomalies = []
    case_financial_map = {}

    for case in fir_cases:
        case_id = case["FIR_No"]
        tier = determine_financial_tier(case)
        role, name, phone = select_financial_suspect(case, case_suspicious_map)
        account_no = generate_account_number()
        bank_name, ifsc = random.choice(BANKS_IFSC)
        vpa = generate_vpa(name)

        case_financial_map[case_id] = {
            "tier": tier, "flagged_role": role, "flagged_name": name, "account_no": account_no
        }

        financial_summary.append({
            "Case_ID": case_id, "Financial_Tier": tier, "Flagged_Person": f"{name} ({role})",
            "Linked_Account": account_no if tier != "NONE" else "N/A",
            "Linked_VPA": vpa if tier != "NONE" else "N/A",
            "Crypto_Involved": "PENDING" if tier == "COMPLEX" else "NO",
            "Shell_Company_Involved": "PENDING" if tier == "COMPLEX" else "NO"
        })

        if tier == "NONE":
            continue

        try:
            occ_date = datetime.strptime(case["Date_Time_of_FIR"].split(" ")[0], "%Y-%m-%d")
        except (ValueError, IndexError):
            occ_date = datetime.strptime("2026-09-08", "%Y-%m-%d")
        base_time = (occ_date - timedelta(days=random.randint(0, 3))).replace(hour=10, minute=0, second=0)

        balance = random.randint(20000, 150000)

        # ---- Bank Statement Records (BASIC and above) ----
        n_bank = {"BASIC": 3, "MODERATE": 6, "COMPLEX": 10}[tier]
        for i in range(n_bank):
            txn_time = base_time + timedelta(minutes=i * random.randint(20, 90))
            is_cr = random.random() < 0.4
            amount = random.randint(5000, 60000)
            balance = balance + amount if is_cr else max(balance - amount, 500)
            counterparty = random.choice(MERCHANT_NAMES) if random.random() < 0.5 else f"Individual-{random.randint(1000,9999)}"
            bank_records.append({
                "Case_ID": case_id, "Person": f"{name} ({role})",
                "Transaction_DateTime": txn_time.strftime("%Y-%m-%d %H:%M:%S"),
                "UTR_Transaction_ID": generate_utr(), "Account_Number": f"XXXX{account_no[-4:]}",
                "Type_CR_DR": "CR" if is_cr else "DR", "Amount_INR": amount, "Balance_INR": balance,
                "Counterparty_Name": counterparty, "Counterparty_Account_UPI": generate_vpa(counterparty),
                "Channel": random.choice(["UPI", "IMPS", "NEFT", "ATM Cash", "RTGS"])
            })

        # ---- RULE 5: Structuring / smurfing (sub-threshold cash-outs) ----
        if tier in ["MODERATE", "COMPLEX"] and random.random() < (0.55 if tier == "COMPLEX" else 0.25):
            structure_total = 0
            for i in range(3):
                amt = random.randint(41000, 49000)
                structure_total += amt
                t = base_time + timedelta(hours=i * 2)
                balance = max(balance - amt, 500)
                bank_records.append({
                    "Case_ID": case_id, "Person": f"{name} ({role})",
                    "Transaction_DateTime": t.strftime("%Y-%m-%d %H:%M:%S"),
                    "UTR_Transaction_ID": generate_utr(), "Account_Number": f"XXXX{account_no[-4:]}",
                    "Type_CR_DR": "DR", "Amount_INR": amt, "Balance_INR": balance,
                    "Counterparty_Name": "ATM Cash Out", "Counterparty_Account_UPI": "N/A",
                    "Channel": "ATM Cash"
                })
            financial_anomalies.append({
                "Case_ID": case_id, "Rule_Violated": "RULE 5: STRUCTURING / SMURFING PATTERN", "Severity": "HIGH",
                "Person": f"{name} ({role})",
                "Details": f"3 cash withdrawals of Rs.41,000-49,000 each (total Rs.{structure_total}) executed within a single day, each kept just under the Rs.50,000 reporting threshold - indicative of deliberate structuring to avoid mandatory reporting."
            })

        # ---- UPI / Payment Gateway logs ----
        n_upi = {"BASIC": 2, "MODERATE": 4, "COMPLEX": 6}[tier]
        for i in range(n_upi):
            t = base_time + timedelta(minutes=i * 30)
            upi_records.append({
                "Case_ID": case_id, "Person": f"{name} ({role})", "Timestamp": t.strftime("%Y-%m-%d %H:%M:%S"),
                "Payer_VPA": vpa, "Payee_VPA": generate_vpa(random.choice(MERCHANT_NAMES)),
                "RRN_Transaction_Ref": generate_utr(), "Device_ID_IMEI": gen_imei(),
                "IP_Address": random.choice(CLEAN_IPS), "Location_City": random.choice(["Mumbai, MH", "New Delhi, DL", "Bengaluru, KA"]),
                "Status": "SUCCESS"
            })

        # ---- RULE 6: Rapid layering / mule-account pattern ----
        if tier in ["MODERATE", "COMPLEX"] and random.random() < (0.6 if tier == "COMPLEX" else 0.3):
            mule_amount = random.randint(20000, 80000)
            cr_time = base_time + timedelta(hours=1)
            dr_time = cr_time + timedelta(minutes=random.randint(2, 12))
            upi_records.append({
                "Case_ID": case_id, "Person": f"{name} ({role})", "Timestamp": cr_time.strftime("%Y-%m-%d %H:%M:%S"),
                "Payer_VPA": generate_vpa(f"unknown{random.randint(100,999)}"), "Payee_VPA": vpa,
                "RRN_Transaction_Ref": generate_utr(), "Device_ID_IMEI": gen_imei(),
                "IP_Address": random.choice(CLEAN_IPS), "Location_City": "Mumbai, MH", "Status": "SUCCESS"
            })
            upi_records.append({
                "Case_ID": case_id, "Person": f"{name} ({role})", "Timestamp": dr_time.strftime("%Y-%m-%d %H:%M:%S"),
                "Payer_VPA": vpa, "Payee_VPA": generate_vpa(f"exit{random.randint(100,999)}"),
                "RRN_Transaction_Ref": generate_utr(), "Device_ID_IMEI": gen_imei(),
                "IP_Address": random.choice(CLEAN_IPS), "Location_City": "Mumbai, MH", "Status": "SUCCESS"
            })
            financial_anomalies.append({
                "Case_ID": case_id, "Rule_Violated": "RULE 6: RAPID LAYERING / MULE ACCOUNT PATTERN", "Severity": "CRITICAL",
                "Person": f"{name} ({role})",
                "Details": f"Rs.{mule_amount} credited to {vpa} at {cr_time.strftime('%H:%M')} was forwarded out again within {(dr_time-cr_time).seconds//60} minutes - account shows no genuine retained balance, consistent with mule-account layering."
            })

        # ---- Merchant / Gateway logs + RULE 7: high-risk device/proxy ----
        if tier in ["MODERATE", "COMPLEX"]:
            n_merchant = 3 if tier == "MODERATE" else 5
            for i in range(n_merchant):
                t = base_time + timedelta(hours=2, minutes=i * 15)
                use_risky_ip = (tier == "COMPLEX" and i == n_merchant - 1 and random.random() < 0.6)
                ip = random.choice(TOR_PROXIES) if use_risky_ip else random.choice(CLEAN_IPS)
                gateway = random.choice(PAYMENT_GATEWAYS)
                merchant = random.choice(MERCHANT_NAMES)
                amount = random.randint(1000, 30000)
                merchant_records.append({
                    "Case_ID": case_id, "Person": f"{name} ({role})", "Timestamp": t.strftime("%Y-%m-%d %H:%M:%S"),
                    "Merchant_Name": merchant, "Gateway": gateway, "Gateway_Txn_ID": f"pay_{random.randint(10**11, 10**12 - 1)}",
                    "Payment_Mode": random.choice(["UPI_COLLECT", "UPI_INTENT", "CARD_DEBIT", "NET_BANKING"]),
                    "Amount_INR": amount, "Device_Fingerprint": f"DEV-{random.choice(['ANDR','IOS','WEB'])}-{random.randint(1000,9999)}",
                    "IP_Address": ip, "IP_Geolocation": "Tor Exit Node / Frankfurt, DE" if ip in TOR_PROXIES else "Mumbai, MH, IN",
                    "Risk_Score": "HIGH" if ip in TOR_PROXIES else "LOW",
                    "Gateway_Response": "SUCCESS_00", "Txn_Status": "SUCCESS"
                })
                if use_risky_ip:
                    financial_anomalies.append({
                        "Case_ID": case_id, "Rule_Violated": "RULE 7: HIGH-RISK DEVICE / PROXY (TOR) TRANSACTION", "Severity": "HIGH",
                        "Person": f"{name} ({role})",
                        "Details": f"Payment of Rs.{amount} via {gateway} to {merchant} originated from a Tor exit node ({ip}) rather than the subscriber's usual geolocation - strong indicator of identity concealment."
                    })

        # ---- Crypto trail (COMPLEX only) + RULE 8: rapid off-ramp ----
        crypto_here = False
        if tier == "COMPLEX" and random.random() < 0.7:
            crypto_here = True
            chain, asset = random.choice(BLOCKCHAINS)
            exchange, fiu_id = random.choice(CRYPTO_EXCHANGES)
            wallet_to = generate_wallet_address(chain)
            crypto_amount = random.randint(5000, 50000)
            deposit_time = base_time + timedelta(hours=4)
            crypto_onchain.append({
                "Case_ID": case_id, "Blockchain": chain, "TxHash": generate_txhash(),
                "Sender_Wallet": generate_wallet_address(chain), "Receiver_Wallet": wallet_to, "Asset": asset,
                "Amount": crypto_amount, "Timestamp": deposit_time.strftime("%Y-%m-%d %H:%M:%S"),
                "Status": "CONFIRMED", "Attribution": f"Unhosted Wallet -> {exchange} Deposit Wallet"
            })
            crypto_kyc.append({
                "Case_ID": case_id, "Exchange_Name": exchange, "FIU_ID": fiu_id, "Account_UID": f"UID_{random.randint(10000000,99999999)}",
                "Registered_Name": name, "KYC_Status": "VERIFIED", "PAN": generate_pan(),
                "Registered_Mobile": phone, "Linked_Bank_Account": f"{bank_name} | A/C: XXXX{account_no[-4:]}",
                "Primary_Deposit_Wallet": wallet_to, "Registration_IP": random.choice(CLEAN_IPS)
            })
            sell_time = deposit_time + timedelta(minutes=random.randint(10, 45))
            withdraw_time = sell_time + timedelta(minutes=random.randint(5, 30))
            crypto_onoff.append({
                "Case_ID": case_id, "Timestamp": deposit_time.strftime("%Y-%m-%d %H:%M:%S"), "Account_UID": f"UID-{case_id}",
                "Type": "Crypto Deposit", "Asset": asset, "Amount": crypto_amount, "Channel": "On-Chain Transfer",
                "Linked_Ref": wallet_to, "Status": "COMPLETED"
            })
            crypto_onoff.append({
                "Case_ID": case_id, "Timestamp": withdraw_time.strftime("%Y-%m-%d %H:%M:%S"), "Account_UID": f"UID-{case_id}",
                "Type": "Fiat Withdrawal", "Asset": "INR", "Amount": crypto_amount * random.randint(83, 87),
                "Channel": "Bank Payout", "Linked_Ref": f"{bank_name} A/C XXXX{account_no[-4:]}", "Status": "COMPLETED"
            })
            financial_anomalies.append({
                "Case_ID": case_id, "Rule_Violated": "RULE 8: RAPID CRYPTO OFF-RAMP / LAYERING", "Severity": "CRITICAL",
                "Person": f"{name} ({role})",
                "Details": f"{crypto_amount} {asset} deposited on-chain at {deposit_time.strftime('%H:%M')}, sold and withdrawn as fiat to a linked bank account by {withdraw_time.strftime('%H:%M')} - total conversion cycle under {(withdraw_time-deposit_time).seconds//60} minutes, consistent with rapid crypto layering."
            })

        # ---- ITR + Shell Company block (COMPLEX only) ----
        shell_here = False
        if tier == "COMPLEX" and random.random() < 0.65:
            shell_here = True
            company_name = generate_company_name()
            pan_company = generate_pan(is_company=True)
            gross_income = random.randint(300000, 1200000)
            sft_txns = random.randint(15000000, 40000000)
            itr_records.append({
                "Case_ID": case_id, "Assessee_Name": company_name, "PAN": pan_company,
                "Assessment_Year": "AY 2025-26", "ITR_Form": "ITR-6",
                "Gross_Total_Income_INR": gross_income, "High_Value_SFT_Txns_INR": sft_txns,
                "Income_to_SFT_Ratio": round(sft_txns / gross_income, 1),
                "ITD_Risk_Rating": "CRITICAL" if sft_txns / gross_income > 15 else "MODERATE"
            })
            if sft_txns / gross_income > 15:
                financial_anomalies.append({
                    "Case_ID": case_id, "Rule_Violated": "RULE 9: ITR / SFT INCOME MISMATCH (UNDISCLOSED INCOME)", "Severity": "HIGH",
                    "Person": f"{company_name} (linked entity)",
                    "Details": f"Declared gross income of Rs.{gross_income:,} is inconsistent with Rs.{sft_txns:,} in high-value SFT/AIS-reported transactions ({round(sft_txns/gross_income,1)}x) - suggests undisclosed income routed through this entity."
                })

            addr = random.choice(SHELL_REGISTERED_ADDRESSES)
            directorships = random.randint(6, 14)
            director_income = random.randint(100000, 200000)
            roc_records.append({
                "Case_ID": case_id, "CIN": generate_cin(), "Company_Name": company_name,
                "Registered_Office_Address": addr, "Director_DIN": generate_din(),
                "Director_Name": name, "Total_Directorships_Held": directorships,
                "Declared_Annual_Income_INR": director_income,
                "MCA_Status": "Active (Flagged for Sec 248 Strike-off Review)" if directorships > 8 else "Active",
                "Revenue_FY1_INR": random.randint(300000, 800000),
                "Revenue_FY2_INR": random.randint(50000000, 150000000),
                "Statutory_Auditor": random.choice(AUDITORS)
            })
            if directorships > 8 and director_income < 200000:
                financial_anomalies.append({
                    "Case_ID": case_id, "Rule_Violated": "RULE 10: SHELL / FRONT COMPANY INDICATORS", "Severity": "CRITICAL",
                    "Person": f"{name} (Director, {company_name})",
                    "Details": f"Director holds {directorships} directorships against a declared annual income of only Rs.{director_income:,}, registered at {addr} - address and income pattern match known shell-company fronting profile."
                })

            cibil_records.append({
                "Case_ID": case_id, "Entity_Name": company_name, "CIBIL_Rank_CMR": random.choice(["CMR-7", "CMR-8", "CMR-9"]),
                "Credit_Institution": random.choice(CREDIT_INSTITUTIONS),
                "Sanctioned_Limit_INR": random.randint(20000000, 150000000),
                "Overdue_Amount_INR": random.randint(10000000, 100000000),
                "Defaulter_Status": "Wilful Defaulter (RBI Suit-Filed)" if random.random() < 0.5 else "SMA-2"
            })

            # ---- RULE 11: Fake e-way bill / circular trading ----
            if random.random() < 0.5:
                hsn, commodity = random.choice(GST_COMMODITIES)
                gst_row = {
                    "Case_ID": case_id, "Supplier_GSTIN": generate_gstin(), "Supplier_Name": company_name,
                    "Recipient_GSTIN": generate_gstin(), "Recipient_Name": generate_company_name(),
                    "Commodity_HSN": f"{hsn} ({commodity})", "Taxable_Value_INR": random.randint(1000000, 8000000),
                    "Vehicle_No": generate_number_plate(), "Route_Distance_KM": random.randint(50, 1500),
                    "Forensic_Flag": "FAKE E-WAY BILL: Registered vehicle class incompatible with declared cargo weight"
                }
                gst_records.append(gst_row)
                financial_anomalies.append({
                    "Case_ID": case_id, "Rule_Violated": "RULE 11: FAKE E-WAY BILL / CIRCULAR TRADING", "Severity": "HIGH",
                    "Person": company_name,
                    "Details": f"E-way bill for {commodity} lists vehicle {gst_row['Vehicle_No']}, whose VAHAN class cannot plausibly carry the declared taxable value of Rs.{gst_row['Taxable_Value_INR']:,} - indicates fake invoicing / circular trading to inflate turnover."
                })

        financial_summary[-1]["Crypto_Involved"] = "YES" if crypto_here else "NO"
        financial_summary[-1]["Shell_Company_Involved"] = "YES" if shell_here else "NO"

    save_csv("Financial_Summary.csv", financial_summary)
    save_csv("Bank_Statement_Records.csv", bank_records)
    save_csv("UPI_Payment_Gateway_Logs.csv", upi_records)
    save_csv("Merchant_Gateway_Transaction_Logs.csv", merchant_records)
    save_csv("Crypto_OnChain_Transactions.csv", crypto_onchain)
    save_csv("Crypto_Exchange_KYC_Records.csv", crypto_kyc)
    save_csv("Crypto_Exchange_OnOffRamp_Logs.csv", crypto_onoff)
    save_csv("ITR_Forensic_Profile.csv", itr_records)
    save_csv("GST_EWayBill_Records.csv", gst_records)
    save_csv("CIBIL_Commercial_Credit_Report.csv", cibil_records)
    save_csv("RoC_Shell_Company_Filings.csv", roc_records)

    financial_records = {
        "summary": financial_summary, "bank": bank_records, "upi": upi_records, "merchant": merchant_records,
        "crypto_onchain": crypto_onchain, "crypto_kyc": crypto_kyc, "crypto_onoff": crypto_onoff,
        "itr": itr_records, "gst": gst_records, "cibil": cibil_records, "roc": roc_records
    }
    return financial_records, financial_anomalies, case_financial_map

# ==========================================
# 7. UNIFIED GOVERNMENT REPORTING SYSTEM
# ==========================================

def generate_unified_investigation_report(fir_cases, cdr_records, case_suspicious_map, master_veh, anomalies, financial_records, case_financial_map):
    report_file = "FINAL_GOVERNMENT_CASE_INVESTIGATION_REPORT.txt"

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("========================================================================================\n")
        f.write("                       CONFIDENTIAL LAW ENFORCEMENT REPORT                              \n")
        f.write("   INTEGRATED FIR, TELECOM (CDR), VEHICLE & FINANCIAL/CRYPTO INTELLIGENCE ANOMALY SYSTEM \n")
        f.write("========================================================================================\n\n")

        for case in fir_cases:
            case_id = case["FIR_No"]
            f.write("----------------------------------------------------------------------------------------\n")
            f.write(f"1. FIR BASIC INFORMATION - CASE ID: {case_id}\n")
            f.write("----------------------------------------------------------------------------------------\n")
            f.write(f"District               : {case['District']}\n")
            f.write(f"Police Station         : {case['Police_Station']}\n")
            f.write(f"Date & Time of FIR     : {case['Date_Time_of_FIR']}\n")
            f.write(f"Act & Sections         : {case['Acts_Sections']}\n")
            f.write(f"Case Type              : {case['Case_Type']}\n")
            f.write(f"Place of Occurrence    : {case['Place_of_Occurrence']}\n")
            f.write(f"Investigating Officer  : {case['Investigating_Officer_Name']} ({case['IO_Badge_No']})\n\n")

            f.write("----------------------------------------------------------------------------------------\n")
            f.write("2. TELECOM & CDR ANOMALY ANALYSIS\n")
            f.write("----------------------------------------------------------------------------------------\n")
            meta = case_suspicious_map[case_id]
            flagged_role = meta["flagged_role"]
            flagged_name_field = {
                "ACCUSED": "Accused_Name_Alias",
                "VICTIM": "Victim_Name",
                "INFORMANT": "Informant_Name"
            }[flagged_role]
            f.write(f"PRIMARY CDR SUSPECT   : {flagged_role} ({case.get(flagged_name_field, 'N/A')})\n")
            f.write(f"FLAGGED CONTACT NO    : {meta[f'{flagged_role.lower()}_phone']}\n")
            f.write(f"SUSPICION FINDING     : Off-hours / anomalous call traffic pattern correlated with offense timeframe.\n\n")

            f.write("----------------------------------------------------------------------------------------\n")
            f.write("3. VEHICLE INTELLIGENCE MATRIX (VAHAN / SARATHI / FASTag / ANPR)\n")
            f.write("----------------------------------------------------------------------------------------\n")
            case_veh = [v for v in master_veh if v.get("Case_ID") == case_id]
            for v in case_veh:
                f.write(f" - Role: {v['Person_Role']:<10} | Name: {v['Person_Name']:<20} | Vehicle Owned: {v['Has_Vehicle']:<3} | Plate: {v['Plate']}\n")
            f.write("\n")

            f.write("----------------------------------------------------------------------------------------\n")
            f.write("4. FINANCIAL & CRYPTOCURRENCY INTELLIGENCE SUMMARY\n")
            f.write("----------------------------------------------------------------------------------------\n")
            fin_meta = case_financial_map.get(case_id, {"tier": "NONE", "flagged_role": "N/A", "flagged_name": "N/A"})
            f.write(f"Financial Forensic Tier   : {fin_meta['tier']}\n")
            if fin_meta["tier"] == "NONE":
                f.write(" [*] NO FINANCIAL FORENSIC TRAIL PULLED FOR THIS CASE (routine offense / no financial angle).\n\n")
            else:
                linked_bank = [b for b in financial_records["bank"] if b["Case_ID"] == case_id]
                linked_upi = [u for u in financial_records["upi"] if u["Case_ID"] == case_id]
                linked_crypto = [c for c in financial_records["crypto_onchain"] if c["Case_ID"] == case_id]
                linked_roc = [r for r in financial_records["roc"] if r["Case_ID"] == case_id]
                f.write(f"Flagged Financial Suspect : {fin_meta['flagged_name']} ({fin_meta['flagged_role']})\n")
                f.write(f"Linked Account            : XXXX{fin_meta['account_no'][-4:]}\n")
                f.write(f"Bank Transactions Pulled  : {len(linked_bank)}\n")
                f.write(f"UPI/Gateway Txns Pulled   : {len(linked_upi)}\n")
                f.write(f"Crypto Trail Present      : {'YES' if linked_crypto else 'NO'}\n")
                f.write(f"Shell/Linked Company      : {linked_roc[0]['Company_Name'] if linked_roc else 'N/A'}\n\n")

            f.write("----------------------------------------------------------------------------------------\n")
            f.write("5. GOVERNMENT AUTOMATED ANOMALY ENGINE FINDINGS (VEHICLE + FINANCIAL)\n")
            f.write("----------------------------------------------------------------------------------------\n")
            case_anomalies = [a for a in anomalies if a["Case_ID"] == case_id]
            if case_anomalies:
                for idx, a in enumerate(case_anomalies, 1):
                    f.write(f" [{idx}] SEVERITY: {a['Severity']} | {a['Rule_Violated']}\n")
                    f.write(f"     Target Person : {a['Person']}\n")
                    f.write(f"     Details       : {a['Details']}\n\n")
            else:
                f.write(" [*] NO VEHICLE/IDENTITY/FINANCIAL ANOMALIES DETECTED FOR THIS CASE ID.\n\n")

            f.write("========================================================================================\n\n")

    print(f"\n[REPORT COMPLETE] Master Investigation Report successfully generated: '{report_file}'")

# ==========================================
# MAIN PIPELINE EXECUTION
# ==========================================

if __name__ == "__main__":
    print("\n==========================================================================")
    print("      LAUNCHING INTEGRATED GOVERNMENT LAW ENFORCEMENT INTELLIGENCE PIPELINE ")
    print("==========================================================================\n")

    print("[1/5] Generating 20 FIR cases with vehicle attributes...")
    fir_cases = generate_fir_dataset(count=20)
    print("  └─ Saved: complete_fir_dataset.csv")

    print("[2/5] Generating Telecom Records (SDR, CDR, IPDR) & flagging CDR suspects...")
    sdr, cdr, ipdr, case_map = generate_telecom_data(fir_cases)
    print("  └─ Saved: Subscriber_Detail_Records.csv, Call_Recording.csv, IP_Detail_Records.csv")

    print("[3/5] Running Multi-Rule Vehicle Intelligence Engine (VAHAN/SARATHI/FASTag/ANPR)...")
    vahan, sarathi, fastag, anpr, master_veh, vehicle_anomalies = generate_vehicle_intelligence_and_detect_anomalies(fir_cases, case_map)
    print("  └─ Saved: Vehicle_Summary.csv, VAHAN_Database.csv, SARATHI_Database.csv, FASTag_Toll_Logs.csv, ANPR_Camera_Feeds.csv")

    print("[4/5] Generating Financial & Cryptocurrency Intelligence (Bank/UPI/Merchant/Crypto/ITR/GST/CIBIL/RoC)...")
    financial_records, financial_anomalies, case_financial_map = generate_financial_intelligence(fir_cases, case_map)
    print("  └─ Saved: Financial_Summary.csv, Bank_Statement_Records.csv, UPI_Payment_Gateway_Logs.csv,")
    print("            Merchant_Gateway_Transaction_Logs.csv, Crypto_OnChain_Transactions.csv, Crypto_Exchange_KYC_Records.csv,")
    print("            Crypto_Exchange_OnOffRamp_Logs.csv, ITR_Forensic_Profile.csv, GST_EWayBill_Records.csv,")
    print("            CIBIL_Commercial_Credit_Report.csv, RoC_Shell_Company_Filings.csv")

    all_anomalies = vehicle_anomalies + financial_anomalies

    print("[5/5] Writing Final Master Investigation Report...")
    generate_unified_investigation_report(fir_cases, cdr, case_map, master_veh, all_anomalies, financial_records, case_financial_map)

    print("\n==========================================================================")
    print("                      PIPELINE EXECUTION SUCCESSFUL                       ")
    print("==========================================================================")

    # ----------------------------------------------------------------
    # [6/6] OPTIONAL: run the analysis modules right after generation,
    # so a single `python main_investigation_pipeline.py` produces both
    # the raw data AND the relationship graph / network analytics /
    # intelligence alerts. Guarded with try/except so this file still
    # works standalone if the analysis modules aren't present yet.
    # ----------------------------------------------------------------
    try:
        print("\n[6/6] Running relationship graph + network analytics + intelligence engine...")
        from sihrelationship import build_relationship_graph
        from sihnetworkanalytics import run_network_analytics
        from sihintelligenceengine import run_full_intelligence_analysis

        graph, cross_case_links = build_relationship_graph()
        net_report = run_network_analytics(graph=graph)
        intel_report = run_full_intelligence_analysis()

        print(f"  └─ relationship_graph.json         ({graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges)")
        print(f"  └─ network_analytics_report.json   ({len(net_report['top_suspects'])} ranked suspects, "
              f"{net_report['summary']['critical_bridge_count']} bridges)")
        print(f"  └─ network_map.html                 (interactive graph)")
        print(f"  └─ intelligence_report.json        ({intel_report['meta']['alert_count']} alerts, "
              f"{intel_report['meta']['critical_or_high_alerts']} critical/high)")
        print(f"  └─ cross-case suspect links found: {len([l for l in cross_case_links if l['cross_case']])}")
    except ImportError as e:
        print(f"\n[6/6] Skipped analysis modules (not found yet): {e}")
