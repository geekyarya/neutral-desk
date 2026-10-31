"""All on-screen, spoken and YouTube text, per language (channel.language in config.yaml)."""
import datetime as dt

MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
           "October", "November", "December"],
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर",
           "नवंबर", "दिसंबर"],
}

STRINGS = {
    "en": {
        "llm_language": "English. Use plain spoken English.",
        "top_stories": "Today's top stories",
        "story_n": "STORY {i} OF {n}",
        "world": "WORLD",
        "reported_by": "Reported by {n} independent outlets",
        "foreign": "+ foreign media",
        "sources": "Sources: {list}",
        "confirmed": "CONFIRMED",
        "unconfirmed": "NOT INDEPENDENTLY CONFIRMED",
        "per": " — per {src}",
        "headlines": "HEADLINES",
        "ai_label": "AI-GENERATED ANCHOR & VOICE",
        "how_title": "How we verify",
        "how_points": [
            "A fact is stated as fact only if {k}+ independent media groups report it.",
            "Outlets with the same owner count as one source.",
            "Single-source claims are attributed or marked unconfirmed.",
            "All source links are in the description.",
        ],
        "fact_checked": "FACT-CHECKED",
        "intro": "Welcome to {name}. It's {date}. Here are today's top stories, cross-checked across "
                 "{n_outlets} news outlets.",
        "outro": "That's the news for today. On {name}, something is reported as fact only when at least {k} "
                 "independent media groups confirm it. Everything else is attributed to its source. All links "
                 "are in the description. Our anchor and voice are AI generated. See you tomorrow.",
        "title": "{headline} | News {date}",
        "title_short": "News {date} | {name}",
        "desc_checked": "Today's stories were cross-checked across {n} outlets.",
        "desc_stories": "STORIES",
        "desc_sources": "SOURCES",
        "desc_how": "HOW WE VERIFY",
        "desc_how_text": "A fact is presented as fact only when at least {k} independent media groups report it "
                         "(outlets with the same owner count once). Single-source claims are attributed to "
                         "their source or marked unconfirmed.",
        "desc_disclosure": "DISCLOSURE",
        "desc_disclosure_text": "The anchor, voice and script of this video are AI-generated from the public "
                                "reports linked above. Errors are possible; please check the sources. "
                                "Corrections welcome in the comments.",
        "hashtags": "#news #indianews #unbiased #factcheck",
        "short_outro": "Full bulletin and all sources on {name}.",
        "short_footer": "Full bulletin & sources on the channel",
        "short_title": "{headline} #Shorts",
        "short_desc_full": "Full bulletin: {url}",
        "weekly_title": "This week's top stories",
        "weekly_intro": "Welcome to {name}. Here are the biggest stories of the week from {start} to {end}, "
                        "each one cross-checked across independent media groups.",
        "weekly_outro": "That was the week on {name}. Every fact was confirmed by at least {k} independent media "
                        "groups. All sources are in the description. See you next week.",
        "weekly_yt_title": "The Week in News | {start} – {end}",
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "reaction_label": "WHAT PEOPLE SAY (REDDIT) — OPINION, NOT FACT",
        "why_label": "WHY IT MATTERS",
        "breaking": "BREAKING",
        "story_word": "STORY",
        "desc_reactions": "Public reaction (opinions)",
        "reel_tags": {"news": "NEWS", "mystery": "MYSTERY", "supernatural": "STRANGE NEWS"},
        "reel_outro": "Follow {name} for more.",
        "reel_source": "Source",
        "reel_disclosure": "Anchor, voice and script are AI-generated from the sources above. Claims about the "
                           "supernatural are reported, not endorsed.",
    },
    "hi": {
        "llm_language": (
            "Hindi, in Devanagari script. Use simple everyday Hindi as spoken on Indian TV news "
            "(Hindustani, not heavy Sanskrit words). In \"script\" write EVERYTHING in Devanagari, "
            "including people's names, places and English terms (e.g. 'आरबीआई', 'सुप्रीम कोर्ट'), "
            "because a Hindi text-to-speech voice will read it. Digits are fine."),
        "top_stories": "आज की मुख्य खबरें",
        "story_n": "खबर {i} / {n}",
        "world": "दुनिया",
        "reported_by": "{n} स्वतंत्र मीडिया समूहों ने रिपोर्ट किया",
        "foreign": "+ विदेशी मीडिया",
        "sources": "स्रोत: {list}",
        "confirmed": "पुष्टि हुई",
        "unconfirmed": "स्वतंत्र रूप से पुष्टि नहीं",
        "per": " — स्रोत: {src}",
        "headlines": "सुर्खियाँ",
        "ai_label": "AI द्वारा बनाए गए एंकर और आवाज़",
        "how_title": "हम कैसे जांचते हैं",
        "how_points": [
            "कोई बात तथ्य तभी, जब कम से कम {k} स्वतंत्र मीडिया समूह उसकी रिपोर्ट करें।",
            "एक ही मालिक के चैनल/अखबार एक ही स्रोत गिने जाते हैं।",
            "एक ही स्रोत वाले दावे स्रोत के नाम के साथ बताए जाते हैं।",
            "सभी स्रोतों के लिंक डिस्क्रिप्शन में हैं।",
        ],
        "fact_checked": "तथ्य-जांच",
        "intro": "नमस्कार, {name} में आपका स्वागत है। आज {date} है। ये हैं आज की मुख्य खबरें, जिन्हें "
                 "{n_outlets} मीडिया संस्थानों की रिपोर्टों से मिलाकर जांचा गया है।",
        "outro": "आज के लिए बस इतना ही। {name} पर कोई बात तथ्य के रूप में तभी बताई जाती है, जब कम से कम {k} "
                 "स्वतंत्र मीडिया समूह उसकी पुष्टि करें। बाकी दावों के साथ उनका स्रोत बताया जाता है। सभी स्रोतों "
                 "के लिंक डिस्क्रिप्शन में हैं। हमारे एंकर और आवाज़ एआई से बनाए गए हैं। कल फिर मिलेंगे, नमस्कार।",
        "title": "{headline} | आज की खबरें {date}",
        "title_short": "आज की खबरें {date} | {name}",
        "desc_checked": "आज की खबरें {n} मीडिया संस्थानों की रिपोर्टों से मिलाकर जांची गई हैं।",
        "desc_stories": "खबरें",
        "desc_sources": "स्रोत",
        "desc_how": "हम कैसे जांचते हैं",
        "desc_how_text": "कोई बात तथ्य के रूप में तभी बताई जाती है जब कम से कम {k} स्वतंत्र मीडिया समूह उसकी "
                         "रिपोर्ट करें (एक ही मालिक के संस्थान एक गिने जाते हैं)। एक ही स्रोत वाले दावे स्रोत के "
                         "नाम के साथ या 'पुष्टि नहीं' लिखकर बताए जाते हैं।",
        "desc_disclosure": "सूचना",
        "desc_disclosure_text": "इस वीडियो के एंकर, आवाज़ और स्क्रिप्ट ऊपर दिए गए सार्वजनिक स्रोतों से AI द्वारा "
                                "बनाए गए हैं। गलती संभव है, कृपया स्रोत ज़रूर देखें। सुधार कमेंट में बताएं।",
        "hashtags": "#hindinews #news #indianews #निष्पक्ष_खबर #factcheck",
        "short_outro": "पूरी खबरें और सभी स्रोत, {name} पर।",
        "short_footer": "पूरा बुलेटिन और स्रोत चैनल पर",
        "short_title": "{headline} #Shorts",
        "short_desc_full": "पूरा बुलेटिन: {url}",
        "weekly_title": "इस हफ्ते की बड़ी खबरें",
        "weekly_intro": "नमस्कार, {name} में आपका स्वागत है। ये हैं {start} से {end} तक, इस हफ्ते की सबसे बड़ी खबरें, "
                        "हर खबर स्वतंत्र मीडिया समूहों की रिपोर्टों से मिलाकर जांची हुई।",
        "weekly_outro": "ये था इस हफ्ते का हाल। {name} पर हर तथ्य की पुष्टि कम से कम {k} स्वतंत्र मीडिया समूहों ने की है। "
                        "सभी स्रोतों के लिंक डिस्क्रिप्शन में हैं। अगले हफ्ते फिर मिलेंगे, नमस्कार।",
        "weekly_yt_title": "हफ्ते की बड़ी खबरें | {start} – {end}",
        "weekdays": ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],
        "reaction_label": "लोगों की राय (Reddit) — राय, तथ्य नहीं",
        "why_label": "इसका मतलब?",
        "breaking": "ब्रेकिंग",
        "story_word": "खबर",
        "desc_reactions": "लोगों की राय (राय, तथ्य नहीं)",
        "reel_tags": {"news": "खबर", "mystery": "रहस्य", "supernatural": "अजब-गजब खबर"},
        "reel_outro": "ऐसी और कहानियों के लिए फॉलो करें {name}।",
        "reel_source": "स्रोत",
        "reel_disclosure": "एंकर, आवाज़ और स्क्रिप्ट ऊपर दिए स्रोतों से AI द्वारा बनाए गए हैं। अलौकिक दावे सिर्फ रिपोर्ट किए गए "
                           "हैं, हम उनकी पुष्टि नहीं करते।",
    },
}


def T(cfg):
    return STRINGS[cfg["channel"]["language"]]


def date_text(cfg, date=None, short=False):
    d = date or dt.date.today()
    month = MONTHS[cfg["channel"]["language"]][d.month - 1]
    return f"{d.day} {month[:3] if short and cfg['channel']['language'] == 'en' else month} {d.year}"
