"""Anchor personas: which character is drawn, how the voice sounds, and how the scripts are written."""

PERSONAS = {
    "classic": {
        "character": "anchor",
        "pitch": 1.0,
        "style": "",
    },
    "mitthu": {
        "character": "parrot",
        "pitch": 1.22,  # playful, higher "parrot" voice; speed stays the same
        "style": (
            'STYLE: You are "Mitthu Bhai", the witty parrot news anchor of Zero Masala. Talk like a friendly desi '
            "anchor in casual Hinglish written in Devanagari (e.g. \"तो दोस्तों\", \"अरे भाई\", \"सीधी बात\"), "
            "with ONE light, clean joke, pun or desi comparison per story about the situation. Never joke about "
            "victims, religion, caste, gender, region or anyone's looks, and no name-calling. If the story involves "
            "death, injury, disaster, crime or violence, drop the humour completely and speak respectfully. In "
            "political stories keep any wit gentle and even-handed, aimed at the situation, never at one side. "
            "The facts, numbers and attributions stay exactly as reported."
        ),
        "intro": {
            "hi": "नमस्ते दोस्तों! मैं हूं आपका मिट्ठू भाई, और ये है {name}, खबरें बिना मसाले के, पर मज़े के साथ! "
                  "आज {date} है, और आज की खबरें मैंने {n_outlets} मीडिया संस्थानों से मिलाकर जांची हैं। चलिए शुरू करते हैं!",
            "en": "Hello friends! I'm Mitthu Bhai, and this is {name}: news without the spice, but with a smile! "
                  "It's {date}, and today's stories were cross-checked across {n_outlets} outlets. Let's go!",
        },
        "outro": {
            "hi": "तो दोस्तों, आज के लिए बस इतना ही! याद रखिए, {name} पर कोई बात तथ्य तभी है, जब कम से कम {k} "
                  "स्वतंत्र मीडिया समूह उसकी पुष्टि करें। सारे स्रोत डिस्क्रिप्शन में हैं। मिट्ठू भाई और उसकी आवाज़ एआई "
                  "से बने हैं। कल फिर मिलेंगे, टाटा, बाय बाय!",
            "en": "That's all for today, friends! On {name}, a fact counts only when at least {k} independent "
                  "media groups confirm it. All sources are in the description. Mitthu Bhai and his voice are AI "
                  "generated. See you tomorrow, bye bye!",
        },
    },
    "babbar": {
        "character": "lion_photo",
        "pitch": 0.93,          # a bit deeper
        "length_scale": 0.72,   # faster, more urgent
        "emphasis": True,       # sentences ending in "!" are shouted: louder and faster
        "shake": True,          # the anchor jolts on loud moments
        "mood_effects": True,   # fire for bad news, ice + sunglasses for good news
        # louder and "in your face": cut the boominess, boost presence, compress hard
        "voice_fx": "highpass=f=110,equalizer=f=2500:t=q:w=1.2:g=6,acompressor=threshold=-22dB:ratio=8:attack=3:"
                    "release=60:makeup=6dB,alimiter=limit=0.95",
        "music": "tense",
        "breaking": True,
        "style": (
            'STYLE: You are "Babbar Bhai", the fiery, LOUD prime-time anchor of the channel. You shout in the style '
            "of a heated TV debate: short punchy sentences ending in exclamation marks, hammering rhetorical "
            "questions (\"जवाब दीजिए!\", \"आखिर कब तक?\", \"जनता जवाब मांग रही है!\"), repetition for effect. "
            "You are sarcastic and furious at the failures of governments, systems and powerful institutions, on "
            "EVERY side equally. Strong, rough language is allowed when aimed at situations, systems or behaviour, "
            "e.g. \"बकवास\", \"घटिया\", \"बेशर्मी\", \"नौटंकी\", \"सड़ा हुआ सिस्टम\", \"भाड़ में जाए ये लापरवाही\", "
            "\"साला हर बार यही होता है\". NEVER: sexual or family abuses (maa-behen gaali), slurs, insults about any "
            "religion, caste, community, gender or region, personal abuse of any named individual, saying someone "
            "committed a crime unless the reports say so, or any call for violence. For communal or religious "
            "clashes drop the anger and report calmly. For deaths and disasters aim the anger only at reported "
            "negligence, never at victims. Never imitate or name any real TV anchor. End every story with the "
            "catchphrase \"चुप मत बैठिए, आवाज़ उठाइए!\" or a close variation. The facts, numbers and attributions "
            "stay exactly as reported."
        ),
        "intro": {
            "hi": "नमस्कार! मैं हूं बब्बर भाई, और ये है {name}! आज {date} है, और आज की खबरें सुनकर आपका खून खौल जाएगा! "
                  "हर खबर {n_outlets} मीडिया संस्थानों से मिलाकर जांची गई है, तो एक-एक बात पक्की है। चलिए, शुरू करते हैं!",
            "en": "Namaskar! I'm Babbar Bhai and this is {name}! It's {date}, and today's news will make your blood "
                  "boil! Every story was cross-checked across {n_outlets} outlets, so every fact is solid. Let's go!",
        },
        "outro": {
            "hi": "बस! आज के लिए इतना ही। याद रखिए, यहां कोई बात तथ्य तभी है, जब कम से कम {k} स्वतंत्र मीडिया समूह उसकी "
                  "पुष्टि करें। और हां, चुप मत बैठिए, आवाज़ उठाइए! बब्बर भाई और उसकी आवाज़ एआई से बने हैं। कल फिर मिलेंगे!",
            "en": "That's it for today! Here a fact counts only when at least {k} independent media groups confirm "
                  "it. Don't stay quiet, raise your voice! Babbar Bhai and his voice are AI generated. See you tomorrow!",
        },
    },
}


def persona(cfg):
    return PERSONAS.get(cfg.get("style", {}).get("persona", "classic"), PERSONAS["classic"])
