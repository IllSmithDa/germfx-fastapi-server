# app/util/side_effect_terms.py

SIDE_EFFECT_TERMS = {
    # -------------------------
    # GI / digestive
    # -------------------------
    "nausea": ["nausea", "queasiness"],
    "vomiting": ["vomiting", "vomit"],
    "diarrhea": ["diarrhea", "diarrhoea", "loose stools"],
    "constipation": ["constipation"],
    "abdominal pain": ["abdominal pain", "stomach pain", "belly pain"],
    "abdominal discomfort": ["abdominal discomfort", "stomach discomfort"],
    "indigestion": ["indigestion", "dyspepsia", "upset stomach"],
    "heartburn": ["heartburn", "acid reflux", "gastroesophageal reflux"],
    "decreased appetite": ["decreased appetite", "loss of appetite", "anorexia"],
    "dry mouth": ["dry mouth", "xerostomia"],
    "bloating": ["bloating", "abdominal bloating", "abdominal distension"],
    "gas": ["flatulence", "gas"],
    "nausea and vomiting": ["nausea and vomiting"],
    "gastrointestinal disorder": ["gastrointestinal upset", "gastrointestinal disorder", "gi upset"],
    "colitis": ["colitis", "inflammation of colon", "inflammatory bowel"],
    "rectal bleeding": ["rectal bleeding", "rectal haemorrhage", "rectal hemorrhage"],
    "difficulty swallowing": ["difficulty swallowing", "dysphagia"],
    "mouth ulcers": ["mouth ulcers", "oral ulceration", "aphthous ulcer", "stomatitis"],
    "pancreatitis": ["pancreatitis"],
    "increased appetite": ["increased appetite", "hyperphagia"],

    # -------------------------
    # Neuro / general
    # -------------------------
    "headache": ["headache", "head pain", "migraine"],
    "dizziness": ["dizziness", "lightheadedness", "light-headedness", "vertigo"],
    "drowsiness": ["drowsiness", "somnolence", "sleepiness", "sedation"],
    "insomnia": ["insomnia", "sleeplessness", "trouble sleeping", "sleep disorder", "sleep disturbance"],
    "fatigue": ["fatigue", "tiredness", "tired", "lack of energy", "lethargy", "malaise", "asthenia"],
    "weakness": ["weakness", "asthenia", "muscular weakness", "muscle weakness"],
    "tremor": ["tremor", "shaking", "trembling"],
    "confusion": ["confusion", "confusional state", "disorientation", "cognitive disorder", "mental status change"],
    "anxiety": ["anxiety", "nervousness", "agitation", "restlessness"],
    "depression": ["depression", "depressed mood", "major depression"],
    "irritability": ["irritability", "mood swings", "emotional lability"],
    "memory problems": ["memory impairment", "memory problems", "amnesia"],
    "numbness": ["numbness", "hypoesthesia", "peripheral neuropathy", "tingling", "paresthesia", "pins and needles"],
    "hallucinations": ["hallucinations", "visual hallucinations", "auditory hallucinations"],
    "suicidal thoughts": ["suicidal ideation", "suicidal thoughts", "thoughts of suicide", "self harm"],
    "mood changes": ["mood changes", "mood altered", "affect lability"],
    "concentration problems": ["concentration difficulty", "difficulty concentrating", "disturbance in attention"],
    "coordination problems": ["ataxia", "coordination problems", "balance disorder", "gait disturbance"],
    "speech problems": ["dysarthria", "speech disorder", "speech problems"],
    "feeling abnormal": ["feeling abnormal", "feeling strange"],
    "ear ringing": ["tinnitus", "ringing in ears", "ear ringing"],
    "cognitive impairment": ["cognitive impairment", "cognitive disorder"],
    "dark urine": ["dark urine", "discolored urine", "tea colored urine"],

    # -------------------------
    # Skin / allergy
    # -------------------------
    "rash": ["rash", "skin rash", "dermatitis", "eczema", "exanthem"],
    "itching": ["itching", "pruritus"],
    "hives": ["hives", "urticaria"],
    "skin irritation": ["skin irritation", "irritated skin"],
    "skin redness": ["skin redness", "erythema", "reddening", "skin reddening"],
    "dry skin": ["dry skin", "skin dryness", "xeroderma"],
    "skin peeling": ["skin peeling", "peeling skin", "desquamation"],
    "blisters": ["blisters", "vesicles", "bullous eruption"],
    "swelling": ["swelling", "edema", "oedema", "peripheral swelling", "peripheral oedema"],
    "facial swelling": ["facial swelling", "face swelling", "face oedema", "facial oedema"],
    "bruising": ["bruising", "contusion", "ecchymosis"],
    "sun sensitivity": ["photosensitivity", "sun sensitivity", "photosensitivity reaction"],
    "acne": ["acne", "acneiform rash"],
    "skin darkening": ["hyperpigmentation", "skin discolouration", "skin darkening"],
    "night sweats": ["night sweats", "nocturnal hyperhidrosis"],
    "stevens-johnson syndrome": ["stevens-johnson syndrome", "toxic epidermal necrolysis", "erythema multiforme"],
    "skin infection": ["skin infection", "cellulitis"],
    "nail changes": ["nail disorder", "nail discolouration", "brittle nails"],

    # -------------------------
    # Respiratory / ENT
    # -------------------------
    "cough": ["cough", "productive cough", "dry cough"],
    "shortness of breath": [
        "shortness of breath",
        "dyspnoea",
        "difficulty breathing",
        "trouble breathing",
        "breathlessness",
        "respiratory distress",
    ],
    "nasal congestion": ["nasal congestion", "stuffy nose", "nasal obstruction"],
    "runny nose": ["runny nose", "rhinorrhea", "rhinorrhoea", "nasal discharge"],
    "sore throat": ["sore throat", "pharyngitis", "throat pain"],
    "common cold": ["nasopharyngitis", "common cold", "upper respiratory tract infection", "urti"],
    "sinus pain": ["sinus pain", "sinusitis"],
    "wheezing": ["wheezing", "bronchospasm"],
    "hoarseness": ["hoarseness", "dysphonia", "voice changes"],
    "nosebleed": ["epistaxis", "nosebleed", "nasal bleeding"],
    "pneumonia": ["pneumonia", "lung infection"],
    "blood clot in lung": ["pulmonary embolism", "blood clot in lung"],
    "throat discomfort": ["oropharyngeal pain", "throat discomfort"],

    # -------------------------
    # Pain / musculoskeletal
    # -------------------------
    "chest pain": ["chest pain", "chest discomfort", "chest tightness"],
    "back pain": ["back pain", "lower back pain", "lumbar pain"],
    "joint pain": ["joint pain", "arthralgia", "arthritis"],
    "muscle pain": ["muscle pain", "myalgia", "musculoskeletal pain", "body aches"],
    "pain in extremity": ["pain in extremity", "arm pain", "leg pain", "limb pain"],
    "muscle spasms": ["muscle spasms", "muscle cramps", "cramp"],
    "joint swelling": ["joint swelling", "joint inflammation"],
    "injection site pain": ["injection site pain", "injection site discomfort"],
    "injection site redness": ["injection site erythema", "injection site redness", "injection site reaction"],
    "neck pain": ["neck pain", "cervicalgia"],
    "bone pain": ["bone pain", "ossalgia"],
    "tendon pain": ["tendinitis", "tendon pain", "tendinopathy"],
    "stiffness": ["stiffness", "musculoskeletal stiffness", "joint stiffness"],
    "fibromyalgia": ["fibromyalgia"],
    "muscle breakdown": ["rhabdomyolysis", "muscle breakdown"],

    # -------------------------
    # Cardiovascular / systemic
    # -------------------------
    "rapid heartbeat": ["palpitations", "heart pounding", "rapid heartbeat"],
    "high blood pressure": ["hypertension", "blood pressure increased", "high blood pressure"],
    "low blood pressure": ["hypotension", "low blood pressure", "blood pressure decreased"],
    "fever": ["fever", "pyrexia", "high temperature"],
    "chills": ["chills", "rigors"],
    "dehydration": ["dehydration"],
    "hot flash": ["flushing", "hot flush", "hot flash"],
    "excessive sweating": ["hyperhidrosis", "excessive sweating", "sweating", "diaphoresis"],
    "irregular heartbeat": ["atrial fibrillation", "arrhythmia", "irregular heartbeat", "tachycardia", "bradycardia"],
    "heart failure": ["heart failure", "cardiac failure", "congestive heart failure"],
    "blood clot": ["thrombosis", "deep vein thrombosis", "dvt", "blood clot", "thromboembolic event"],
    "stroke": ["stroke", "cerebrovascular accident", "cva", "cerebral infarction"],
    "heart attack": ["myocardial infarction", "heart attack", "acute coronary syndrome"],
    "low sodium": ["hyponatraemia", "hyponatremia", "low sodium"],
    "low potassium": ["hypokalaemia", "hypokalemia", "low potassium"],
    "low magnesium": ["hypomagnesaemia", "hypomagnesemia", "low magnesium"],
    "high potassium": ["hyperkalaemia", "hyperkalemia", "high potassium"],
    "elevated liver enzymes": [
        "alanine aminotransferase increased",
        "aspartate aminotransferase increased",
        "liver enzyme elevated",
        "hepatic enzyme increased",
        "alt increased",
        "ast increased",
        "transaminases increased",
    ],
    "elevated creatinine": ["blood creatinine increased", "creatinine increased", "elevated creatinine"],
    "liver damage": ["hepatotoxicity", "liver injury", "hepatitis", "jaundice", "liver damage", "liver failure"],
    "kidney problems": ["renal impairment", "renal failure", "kidney failure", "acute kidney injury"],
    "low blood counts": ["thrombocytopenia", "low platelets", "platelet count decreased"],

    # -------------------------
    # GU / infections
    # -------------------------
    "urinary tract infection": ["urinary tract infection", "uti", "cystitis", "bladder infection"],
    "frequent urination": ["frequent urination", "pollakiuria", "urinary frequency"],
    "painful urination": ["painful urination", "dysuria"],
    "vaginal discharge": ["vaginal discharge", "vaginal infection", "vaginal candidiasis"],
    "urinary retention": ["urinary retention", "difficulty urinating"],
    "urinary incontinence": ["urinary incontinence", "loss of bladder control"],
    "kidney infection": ["pyelonephritis", "kidney infection"],
    "blood in urine": ["haematuria", "hematuria", "blood in urine"],
    "erectile dysfunction": ["erectile dysfunction", "impotence", "sexual dysfunction"],
    "menstrual irregularities": ["menstrual irregularity", "menstruation irregular", "amenorrhoea", "amenorrhea"],
    "yeast infection": ["candidiasis", "yeast infection", "oral candidiasis", "thrush"],
    "bloodstream infection": ["sepsis", "septicaemia", "bloodstream infection"],

    # -------------------------
    # Vision
    # -------------------------
    "blurred vision": ["blurred vision", "vision blurred", "visual disturbance"],
    "visual impairment": ["visual impairment", "vision loss", "visual acuity reduced"],
    "eye irritation": ["eye irritation", "eye pain", "ocular discomfort"],
    "eye redness": ["eye redness", "conjunctival redness", "conjunctivitis", "red eye"],
    "dry eyes": ["dry eyes", "dry eye", "keratoconjunctivitis sicca"],
    "double vision": ["diplopia", "double vision"],
    "sensitivity to light": ["photophobia", "light sensitivity", "sensitivity to light"],
    "cataracts": ["cataract", "lens opacity"],
    "glaucoma": ["glaucoma", "ocular hypertension"],

    # -------------------------
    # Hair / weight
    # -------------------------
    "hair loss": ["hair loss", "alopecia", "hair thinning"],
    "weight loss": ["weight decreased", "weight loss", "body weight decreased"],
    "weight gain": ["weight increased", "weight gain", "body weight increased"],
    "hair growth": ["hypertrichosis", "hirsutism", "excessive hair growth"],

    # -------------------------
    # Other clinically common terms
    # -------------------------
    "allergic reaction": ["allergic reaction", "drug hypersensitivity", "hypersensitivity", "anaphylaxis", "anaphylactic reaction"],
    "seizure": ["seizure", "seizures", "convulsion", "epileptic seizure"],
    "loss of consciousness": ["loss of consciousness", "fainting", "syncope", "unconsciousness"],
    "infection": ["infection", "bacterial infection", "viral infection"],
    "red blood cell count decreased": ["anaemia", "anemia", "red blood cell count decreased", "haemoglobin decreased"],
    "low white blood cells": ["neutropenia", "low white blood cells", "leukopenia", "white blood cell count decreased"],
    "high blood sugar": ["blood glucose increased", "high blood sugar", "hyperglycaemia", "hyperglycemia", "diabetes mellitus"],
    "low blood sugar": ["hypoglycaemia", "hypoglycemia", "low blood sugar", "blood glucose decreased"],
    "thyroid problems": ["hypothyroidism", "hyperthyroidism", "thyroid disorder"],
    "muscle breakdown": ["rhabdomyolysis", "creatine phosphokinase increased", "cpk increased"],
    "swollen lymph nodes": ["lymphadenopathy", "swollen lymph nodes", "lymph node enlargement"],
    "drug reaction": ["drug reaction", "drug-induced", "medication reaction", "adverse drug reaction"],

    # -------------------------
    # Psychiatric / behavioural
    # -------------------------
    "paranoia": ["psychosis", "psychotic disorder", "paranoia", "delusions"],
    "bipolar episode": ["mania", "manic episode", "bipolar episode"],
    "panic attacks": ["panic attack", "panic disorder"],
    "emotional disturbance": ["emotional disorder", "emotional disturbance", "affect disorder"],
    "aggression": ["aggression", "aggressive behaviour", "hostility"],
    "nightmares": ["nightmares", "abnormal dreams", "vivid dreams"],
    "apathy": ["apathy", "loss of interest", "flat affect"],
    "restless legs": ["restless legs syndrome", "restless legs", "akathisia"],
    "euphoria": ["euphoria", "feeling high"],

    # -------------------------
    # Endocrine / metabolic
    # -------------------------
    "increased thirst": ["polydipsia", "increased thirst", "excessive thirst"],
    "increased hunger": ["polyphagia", "increased hunger", "excessive hunger"],
    "excessive urination": ["polyuria", "excessive urination"],
    "bone density decreased": ["osteoporosis", "bone density decreased", "bone loss"],
    "adrenal suppression": ["adrenal suppression", "adrenal insufficiency"],
    "cushingoid features": ["cushingoid", "moon face", "weight redistribution"],
    "gout": ["gout", "uric acid increased", "hyperuricaemia", "hyperuricemia"],

    # -------------------------
    # Immune / autoimmune
    # -------------------------
    "lupus-like reaction": ["drug-induced lupus", "lupus-like syndrome"],
    "blood vessel inflammation": ["vasculitis", "blood vessel inflammation"],
    "lung inflammation": ["interstitial lung disease", "pulmonary fibrosis", "lung inflammation"],
    "inflammatory reaction": ["inflammation", "inflammatory reaction", "immune reaction"],

    # -------------------------
    # GI / bleeding / warning signs
    # -------------------------  
    "black or bloody stools": [
        "black or bloody stools",
        "bloody stools",
        "black tarry stools",
        "blood in stool",
        "black stools",
        "black tarry stools",
    ],
    # -------------------------
    # Neuro / general warning signs
    # -------------------------
    "feeling faint": [
        "feel faint",
        "feeling faint",
        "faint",
        "fainting",
    ],
    "slurred speech": [
        "slurred speech",
    ],
    "weakness in a part of body": [
        "weakness on one part of body",
        "weakness in one part of body",
        "one side of body",
        "one part or side of body",
    ],
    "leg swelling": [
        "leg swelling",
        "swelling of the legs",
        "swollen legs",
    ],
}

SERIOUS_SIDE_EFFECTS = {
    # ── Original entries (unchanged) ──────────────────────────────────────────
    "allergic reaction",
    "facial swelling",
    "hives",
    "blisters",
    "shortness of breath",
    "chest pain",
    "seizure",
    "loss of consciousness",
    "low white blood cells",
    "infection",
    "slurred speech",
    "weakness in a part of body",
    "leg swelling",
    "feeling faint",
    "black or bloody stools",

    # ── Cardiovascular ────────────────────────────────────────────────────────
    "heart attack",
    "stroke",
    "heart failure",
    "blood clot",
    "blood clot in lung",
    "irregular heartbeat",

    # ── Neurological ─────────────────────────────────────────────────────────
    "suicidal thoughts",
    "hallucinations",
    "paranoia",
    "seizure",
    "confusion",

    # ── Hepatic / renal ───────────────────────────────────────────────────────
    "liver damage",
    "kidney problems",

    # ── Skin (severe) ─────────────────────────────────────────────────────────
    "stevens-johnson syndrome",

    # ── Respiratory ───────────────────────────────────────────────────────────
    "pneumonia",
    "lung inflammation",

    # ── Haematological ────────────────────────────────────────────────────────
    "red blood cell count decreased",
    "low blood counts",
    "muscle breakdown",          # rhabdomyolysis — can cause acute kidney injury
    "bloodstream infection",

    # ── Endocrine / metabolic ─────────────────────────────────────────────────
    "low blood sugar",           # severe hypoglycaemia can be life-threatening
    "low sodium",                # severe hyponatraemia can cause cerebral oedema
    "low potassium",             # can cause fatal arrhythmias

    # ── GI ────────────────────────────────────────────────────────────────────
    "pancreatitis",
    "rectal bleeding",
}