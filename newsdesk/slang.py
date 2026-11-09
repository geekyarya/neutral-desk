"""The anchor's slang lexicon: Gen Z / internet Hinglish, desi expressions and Bollywood-dialogue style lines.
Each line is "phrase | when it fits". Every prompt gets a random handful, so the anchor keeps sounding different.
Add more lines any time (one per line); they are picked up automatically."""
import random

LEXICON = """
# --- hype, praise, wins
W खबर | good news, a win
बिल्कुल GOAT | someone/something the greatest
ऑरा +1000 | impressive, cool move
सिग्मा मूव | confident, unbothered action
मेन कैरेक्टर एनर्जी | someone acting like the hero
लेवल अनलॉक्ड | a new milestone
माइक ड्रॉप मोमेंट | a killer comeback or statement
पैसा वसूल | totally worth it
गेम चेंजर | something that changes everything
क्या बात है भाई | genuine appreciation
छा गए गुरु | someone did great
फायर है भाई | excellent
ट्रेंड में आ गया | going viral
रिज़ मैक्स | charming, smooth
भौकाल मचा दिया | made a huge splash
धमाका कर दिया | did something spectacular
बॉस मूव | smart powerful move
क्लीन स्वीप | winning everything
हवा बदल दी | changed the mood or momentum
मौज कर दी | great fun or outcome
कमाल कर दिया | did something amazing
ज़बरदस्त फॉर्म | someone in top form
सबका बाप | the ultimate one
पूरा माहौल बन गया | the atmosphere got charged
# --- fails, bad news, L moments
L टेक | bad opinion or decision
ऑरा माइनस | embarrassing, loses cool
NPC वाली हरकत | thoughtless, scripted behaviour
रेशियो हो गया | got heavily outvoted/criticised
कुकिंग चल रही है | someone is cooking (doing well or being roasted)
भुना दिया गया | got roasted
हवा टाइट | someone is scared or nervous
फ्यूज़ उड़ गया | shocked or lost temper
दिमाग का दही | mentally confusing mess
बैंड बज गया | thoroughly embarrassed or defeated
पोल खुल गई | secrets exposed
ज़ीरो रिज़ | zero charm
चप्पल से मारेंगे | a mock threat of scolding for a bad idea
भाई कैप है ये | that's a lie
सरासर कैप | blatant lie
फ्लॉप शो | something that failed badly
पूरा फ़ेल | total failure
ढक्कन निकला | turned out to be useless
डिलीट कर दो ये | something cringe
वाइब चेक फेल | the vibe is off
मूड ऑफ | spoiled mood
रोना बनता है | a sad but funny situation
दुखी आत्मा | disappointed person
पैर पर कुल्हाड़ी | self-inflicted damage
उल्टा पड़ गया दांव | plan backfired
# --- shock, surprise, drama
ये क्या हो रहा है भाई | confusion about a weird situation
सीन बन गया भाई | a big drama unfolds (use rarely, only when truly apt)
बवाल मच गया | uproar
कहानी में ट्विस्ट | plot twist
खेला हो गया | a sudden twist or trick
पूरा ड्रामा चालू | full on drama
पॉपकॉर्न निकालो | watch the drama unfold
रोंगटे खड़े हो गए | goosebumps
होश उड़ गए | shocked
आँखें फटी रह गईं | wide-eyed shock
ब्रूह, सीरियसली | disbelief
भाई साहब, ये क्या | disbelief, formal sarcasm
अरे ओ साम्भा | Sholay-style dramatic call
कितने आदमी थे | Sholay reference, counting something
ये तो होना ही था | inevitable event
सब कुछ चंगा सी | sarcastic "everything is fine"
हद हो गई यार | this is the limit
इतना सन्नाटा क्यों है भाई | Sholay line for sudden silence
बिल्कुल फिल्मी | like a movie scene
कलयुग है भाई | modern times are weird
ट्विस्ट पे ट्विस्ट | many twists
सस्पेंस थ्रिलर | tense unfolding story
कहानी घर घर की | family-saga style drama
# --- desi sarcasm and chaos
भाई कुछ भी | anything goes
डेलूलू है क्या | delusional
टच ग्रास भाई | go outside, get real
चिल मार भाई | calm down
शांति रखो | stay calm, mock-solemn
रसोड़े में कौन था | Saath Nibhana meme, who was in the kitchen
हेरा फेरी वाला सीन | confusing money/messy situation, Hera Pheri
ये बाबू राव का स्टाइल है | Hera Pheri style confusion
उल्टा चोर कोतवाल को डांटे | culprit blames the authority
अंधेर नगरी चौपट राजा | chaotic incompetent rule
ऊपर वाला देख रहा है | karma is watching
जुगाड़ लगा दिया | a clever improvised fix
देसी जुगाड़ | desi improvisation
मौसम बदल गया | the situation changed
ठंडा कर दिया | calmed or silenced someone
घर की मुर्गी दाल बराबर | undervaluing what you have
बात में दम है | a solid point
अपना टाइम आएगा | an underdog's confidence
पिक्चर अभी बाकी है | more to come
ये बात हज़म नहीं हुई | hard to believe
जो जीता वही सिकंदर | the winner takes it
हम तो डूबेंगे सनम | taking everyone down with you
कुछ तो गड़बड़ है दया | CID reference, something is off
दरवाज़ा तोड़ दो | CID style, break it open
एक नंबर | top quality
लाजवाब | wonderful
बेमिसाल | unmatched
झकास | cool, Mumbai slang
टपोरी स्टाइल | street-smart Mumbai attitude
अपुन को पता है | Mumbai swagger
कट्टी पट्टी | friends falling out, silly
सेटिंग हो गई | arrangement done
भाईगिरी | bullying swagger
रंगबाज़ी | showing off with attitude
हल्ला बोल | raise a ruckus
चौकस रहो | stay alert
पतली गली से निकल लो | slip away quietly
# --- internet and Gen Z English-Hinglish
Aura farming | trying to look cool
No cap | not lying, truly
Lowkey | secretly, a bit
Highkey | openly, very
Vibe check | testing mood
Rizz | charm
Delulu | delusional
Cooked | doomed or roasted
Rent free | something occupying minds
Main character syndrome | acting like the star
Side quest | a small unrelated adventure
Plot armor | someone survives everything
Flex | showing off
Cringe | awkward
Based | proudly sticking to your view
Ratio | outvoted in replies
Sus | suspicious
Bet | okay, sure
Slay | doing it brilliantly
Ate and left no crumbs | did it perfectly
It's giving drama | gives the feel of drama
Understood the assignment | did exactly what was needed
Touch grass | go outside
Bro is cooked | someone is doomed
Skill issue | it's their fault, a skill gap
Mid | average
Peak | the best
Bussin | really good
Salty | upset over a small thing
Simp | overly doting
Ghosted | ignored
Rage bait | content made to anger
Doomscrolling | endless bad news scrolling
Glow up | big improvement
Era | a phase, as in "villain era"
NPC | scripted person
Yeet | throw away with force
Receipts | proof
Spill the tea | share gossip
Gatekeep | hide the good stuff
Drip | stylish look
Clapback | a sharp reply
Banger | an excellent piece
Hits different | feels uniquely strong
Sheesh | impressed exclamation
Pookie | cute nickname, light mockery
Brain rot | silly internet content
Girl math | funny self-made logic
Aura loss | embarrassing moment
Lore drop | a big backstory reveal
Chat, is this real | disbelief
# --- cricket and sports flavoured
छक्का मार दिया | hit the ball out of the park, did great
क्लीन बोल्ड | totally defeated
गुगली डाल दी | tricked with a surprise
मैच पलट दिया | turned the game
आखिरी ओवर का थ्रिलर | tension till the end
स्टंप उखाड़ दिए | demolished
पिच रिपोर्ट आ गई | here is the situation
डीआरएस ले लो | ask for a recheck
नो बॉल हो गई | a rule slip
कैच छोड़ा, मैच छोड़ा | a mistake costs everything
धोनी स्टाइल फिनिश | cool finish
कोहली वाला जोश | aggression and passion
रन मशीन | consistent scorer
यॉर्कर मार दिया | a precise killer delivery
पावर प्ले | an early burst of action
सुपर ओवर ड्रामा | edge of the seat tie-break
टॉस जीता बॉस | the toss decided
बैज़बॉल | attacking approach
# --- Bollywood and TV dialogue style
पुष्पा, झुकेगा नहीं | stubborn attitude (Pushpa)
कितने आदमी थे | Sholay
अरे ओ साम्भा | Sholay
पिक्चर अभी बाकी है | to be continued
डॉन को पकड़ना मुश्किल ही नहीं नामुमकिन है | someone slippery (Don)
मोगैम्बो खुश हुआ | a villain is pleased (Mr India)
बड़े बड़े देशों में ऐसी छोटी छोटी बातें | DDLJ, small things happen
जा सिमरन जा | DDLJ, let go and do it
रिश्ते में तो हम तुम्हारे बाप लगते हैं | filmy swagger
तारीख पे तारीख | Damini, delays in justice
हम जहाँ खड़े होते हैं लाइन वहीं से शुरू होती है | confident swagger
सिंघम वाला गुस्सा | angry cop energy
मुन्ना भाई वाली जादू की झप्पी | a hug that fixes things
ऑल इज़ वेल | 3 Idiots reassurance
गजब बेइज्जती है यार | embarrassing, humorous
पावर है भाई | Mirzapur-style power
कालीन भैया वाला सीन | calm but powerful boss attitude
बाबू भैया की सोच | confused but nice
उठा ले रे बाबा | Hera Pheri drama
कहाँ से आते हैं ये लोग | disbelief about odd behaviour
बहुत नाइंसाफी है | exaggerated injustice
इमोशनल अत्याचार | over-the-top sentiment
"""


def _parse():
    items = []
    for line in LEXICON.strip().splitlines():
        if line.startswith("#") or "|" not in line:
            continue
        phrase, note = (x.strip() for x in line.split("|", 1))
        if phrase not in {i[0] for i in items}:
            items.append((phrase, note))
    return items


ITEMS = _parse()
RARE = {"सीन बन गया भाई"}   # allowed, but only occasionally and only when it truly fits


def sample(n=10, avoid=()):
    """Random slang with meanings; the rare ones show up only about 1 time in 8."""
    pool = [i for i in ITEMS if i[0] not in avoid and (i[0] not in RARE or random.random() < 0.12)]
    return random.sample(pool, min(n, len(pool)))


def prompt_hint(used=()):
    picks = sample(10, used)
    lines = "; ".join(f"{p} ({m})" for p, m in picks)
    return ("SLANG you know (use one or two ONLY where they fit the news naturally, never force them, never use "
            "the same one in every video, and you may invent fresh ones): " + lines + ".")
