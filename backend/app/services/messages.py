"""Bilingual (English + Bangla) templates for alerts. Both languages are stored on every alert."""
TEMPLATES = {
    "fever": ("Animal {tag}: temperature {value}°C is above the normal range ({max}°C).",
              "পশু {tag}: তাপমাত্রা {value}°C স্বাভাবিক সীমার ({max}°C) বেশি।"),
    "weight_loss": ("Animal {tag}: weight fell {value}% in the last 7 days.",
                    "পশু {tag}: গত ৭ দিনে ওজন {value}% কমেছে।"),
    "appetite_drop": ("Animal {tag}: feed intake dropped {value}% compared with the last 7 days.",
                      "পশু {tag}: গত ৭ দিনের তুলনায় খাবার গ্রহণ {value}% কমেছে।"),
    "high_risk_prediction": ("Animal {tag}: high disease risk ({disease}, {prob}%). Please contact a veterinarian.",
                             "পশু {tag}: রোগের উচ্চ ঝুঁকি ({disease}, {prob}%)। অনুগ্রহ করে পশুচিকিৎসকের সঙ্গে যোগাযোগ করুন।"),
    "critical_safety_net": ("Animal {tag}: critical signs (high fever with several symptoms). Contact a veterinarian immediately.",
                            "পশু {tag}: গুরুতর লক্ষণ (উচ্চ জ্বরসহ একাধিক উপসর্গ)। এখনই পশুচিকিৎসকের সঙ্গে যোগাযোগ করুন।"),
    "vaccination_due": ("Animal {tag}: {title} is due on {date}.",
                        "পশু {tag}: {title} এর তারিখ {date}।"),
    "vaccination_overdue": ("Animal {tag}: {title} is overdue (was due {date}).",
                            "পশু {tag}: {title} এর সময় পার হয়ে গেছে ({date})।"),
    "missed_entry": ("Animal {tag}: no health record for {days} days.",
                     "পশু {tag}: {days} দিন ধরে কোনো স্বাস্থ্য তথ্য নেই।"),
    "unacknowledged_escalation": ("Animal {tag}: a high alert has not been acknowledged for {hours} hours.",
                                  "পশু {tag}: একটি জরুরি সতর্কতা {hours} ঘণ্টা ধরে দেখা হয়নি।"),
    "iot_anomaly": ("Animal {tag}: sensor {device} shows abnormal readings ({reasons}). Please check the animal.",
                    "পশু {tag}: সেন্সর {device} অস্বাভাবিক মান দেখাচ্ছে ({reasons})। অনুগ্রহ করে পশুটি পরীক্ষা করুন।"),
    "device_offline": ("Animal {tag}: sensor {device} has not sent data for {minutes} minutes.",
                       "পশু {tag}: সেন্সর {device} {minutes} মিনিট ধরে কোনো তথ্য পাঠায়নি।"),
    "device_low_battery": ("Animal {tag}: sensor {device} battery is low ({value}%).",
                           "পশু {tag}: সেন্সর {device} এর ব্যাটারি কম ({value}%)।"),
    "follow_up_due": ("Animal {tag}: follow-up '{title}' is due on {date}.",
                      "পশু {tag}: ফলো-আপ '{title}' এর তারিখ {date}।"),
}
DISCLAIMER = {
    "en": "AI risk estimate to support a veterinarian. It is not a diagnosis. Consult a qualified veterinarian.",
    "bn": "এটি পশুচিকিৎসককে সহায়তার জন্য এআই-ভিত্তিক ঝুঁকির অনুমান। এটি রোগনির্ণয় নয়। অনুগ্রহ করে যোগ্য পশুচিকিৎসকের পরামর্শ নিন।",
}


def render(alert_type: str, params: dict):
    """Returns (message_en, message_bn)."""
    en_t, bn_t = TEMPLATES[alert_type]
    out = []
    for lang, tpl in (("en", en_t), ("bn", bn_t)):
        p = dict(params)
        p["disease"] = params.get("disease_" + lang, "")
        p["reasons"] = params.get("reasons_" + lang, "")
        out.append(tpl.format(**{k: p.get(k, "") for k in ("tag", "value", "max", "disease", "prob", "title", "date", "days", "hours", "reasons", "device", "minutes")}))
    return out[0], out[1]
