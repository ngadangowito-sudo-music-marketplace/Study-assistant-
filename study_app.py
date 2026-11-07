import streamlit as st
from google import genai
from google.genai import types

# ==========================================
# MPANGILIO
# ==========================================
st.set_page_config(page_title="Msaidizi wa Masomo", page_icon="🩺", layout="wide")

st.markdown(
    """
    <style>
    .stButton>button {
        background-color: #1f8a70; color: white; border-radius: 8px;
        padding: 10px 24px; font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🩺 Msaidizi wa Masomo")
st.caption("Pakia rejea zako, kisha upate pointi muhimu, muhtasari, majibu, hesabu na mazoezi.")

MAX_INLINE_MB = 18  # Gemini inakubali takriban 20MB kwa ombi moja


# ==========================================
# SIDEBAR
# ==========================================
def secret_key() -> str:
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        return ""


@st.cache_data(ttl=3600, show_spinner=False)
def list_text_models(key: str):
    """Orodha ya models zinazofaa kwa maandishi, zinazopatikana kwenye akaunti yako."""
    client = genai.Client(api_key=key)
    names = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions:
            names.append(m.name.replace("models/", ""))
    bad = ("image", "tts", "live", "audio", "embed", "imagen", "veo", "robotics", "computer")
    flash = [n for n in names if "flash" in n and not any(b in n for b in bad)]
    return sorted(flash) or sorted(names)


with st.sidebar:
    st.header("⚙️ Mipangilio")
    api_key = st.text_input(
        "Gemini API Key (bure):",
        type="password",
        value=secret_key(),
        help="Pata bure kwenye aistudio.google.com/apikey",
    )

    model = None
    if api_key:
        try:
            models = list_text_models(api_key)
            # Pendelea model ya "flash" isiyo "lite" (ubora zaidi), vinginevyo ya kwanza
            default_idx = next(
                (i for i, n in enumerate(models) if "lite" not in n), 0
            )
            model = st.selectbox("Model:", models, index=default_idx)
        except Exception as e:
            st.error(f"Key haikubaliki au kuna tatizo la mtandao: {e}")

    out_lang = st.selectbox("Lugha ya majibu:", ["Kiswahili", "English", "Kiswahili + English terms"])
    subject = st.text_input("Somo (si lazima):", placeholder="Mfano: Surgery, Paediatrics, Chemistry")

    st.markdown("---")
    st.warning(
        "⚠️ Usipakie taarifa za wagonjwa zinazowatambulisha. "
        "Kwenye huduma ya bure ya Google, data inaweza kutumika kuboresha models zao."
    )

# ==========================================
# REJEA ZA MTUMIAJI
# ==========================================
if "refs" not in st.session_state:
    st.session_state["refs"] = []

with st.expander("📚 Rejea zangu (pakia PDF, picha au maandishi)", expanded=not st.session_state["refs"]):
    uploads = st.file_uploader(
        "Pakia rejea (PDF, PNG, JPG, TXT, MD):",
        type=["pdf", "png", "jpg", "jpeg", "txt", "md"],
        accept_multiple_files=True,
    )
    if uploads:
        refs = []
        for f in uploads:
            data = f.getvalue()
            mime = f.type or ""
            if not mime or f.name.lower().endswith((".txt", ".md")):
                mime = "text/plain"
            refs.append({"name": f.name, "mime": mime, "data": data})
        st.session_state["refs"] = refs

    refs = st.session_state["refs"]
    total_mb = sum(len(r["data"]) for r in refs) / (1024 * 1024)
    if refs:
        st.success(f"Rejea {len(refs)} zimepakiwa ({total_mb:.1f} MB).")
        if total_mb > MAX_INLINE_MB:
            st.error(f"Rejea ni kubwa mno ({total_mb:.1f} MB). Punguza hadi chini ya {MAX_INLINE_MB} MB.")
    else:
        st.info("Hujapakia rejea. Unaweza bado kutumia sehemu ya Hesabu au kuuliza maswali ya jumla.")


# ==========================================
# VIFAA VYA MSAADA
# ==========================================
def system_rules(strict: bool) -> str:
    base = f"""Wewe ni msaidizi wa masomo kwa mwanafunzi wa Clinical Medicine (Tanzania) na masomo mengine ya sayansi.
Lugha ya majibu: {out_lang}. Somo: {subject or 'jumla'}.

KANUNI ZA USAHIHI (ni lazima):
1. Usibuni takwimu, dozi, vipimo, majina ya vitabu wala nukuu. Kama huna uhakika, sema wazi "sina uhakika".
2. Ukitumia rejea za mtumiaji, taja chanzo kwa muundo: [Rejea: jina la faili, ukurasa/sehemu].
3. Rejea zikipingana, onyesha tofauti hiyo wazi na useme ipi ni ya kisasa au ya kuaminika zaidi ikiwa unajua.
4. Taarifa ambayo HAIPO kwenye rejea za mtumiaji iwekwe alama "(Nje ya rejea)".
5. Kwa maada za kitabibu, panga pointi hivi inapowezekana: ufafanuzi, visababishi, dalili na ishara, vipimo, matibabu, matatizo, kinga.
6. Mwishoni mwa jibu la kitabibu, kumbusha kuhakiki dozi na matibabu na miongozo ya taifa (STG) au mwalimu."""
    if strict:
        base += "\n7. TUMIA REJEA ZA MTUMIAJI PEKEE. Jibu halipo kwenye rejea, sema: 'Haipo kwenye rejea ulizopakia.'"
    return base


def build_parts():
    parts = []
    for r in st.session_state["refs"]:
        if r["mime"].startswith("text/"):
            text = r["data"].decode("utf-8", errors="ignore")
            parts.append(types.Part.from_text(text=f"[Rejea: {r['name']}]\n{text}"))
        else:
            parts.append(types.Part.from_text(text=f"[Rejea: {r['name']}]"))
            parts.append(types.Part.from_bytes(data=r["data"], mime_type=r["mime"]))
    return parts


def need_ready(need_refs: bool) -> bool:
    if not api_key or not model:
        st.error("Weka Gemini API Key kwenye Sidebar kwanza.")
        return False
    if need_refs and not st.session_state["refs"]:
        st.warning("Pakia rejea kwanza (sehemu ya 📚 Rejea zangu).")
        return False
    return True


def run(state_key: str, prompt: str, strict: bool, use_refs: bool,
        code_exec: bool = False, temperature: float = 0.2):
    try:
        client = genai.Client(api_key=api_key)
        cfg = types.GenerateContentConfig(
            system_instruction=system_rules(strict),
            temperature=temperature,
            tools=[types.Tool(code_execution=types.ToolCodeExecution())] if code_exec else None,
        )
        contents = (build_parts() if use_refs else []) + [types.Part.from_text(text=prompt)]
        with st.spinner("Inachambua..."):
            resp = client.models.generate_content(model=model, contents=contents, config=cfg)

        code_used = []
        try:
            for p in resp.candidates[0].content.parts:
                if getattr(p, "executable_code", None):
                    code_used.append(p.executable_code.code)
        except Exception:
            pass

        st.session_state[state_key] = {"text": resp.text or "(Hakuna jibu)", "code": code_used}
    except Exception as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            st.error("Umefikia kikomo cha matumizi ya bure kwa sasa. Subiri dakika moja ujaribu tena, au kesho.")
        else:
            st.error(f"Hitilafu: {msg}")
        st.session_state.pop(state_key, None)


def show(state_key: str, file_name: str):
    res = st.session_state.get(state_key)
    if not res:
        return
    st.markdown(res["text"])
    if res["code"]:
        with st.expander("Angalia code iliyotumika kuhesabu"):
            for c in res["code"]:
                st.code(c, language="python")
    st.download_button("📥 Pakua kama faili", res["text"], file_name=file_name,
                       mime="text/markdown", key=f"dl_{state_key}")


# ==========================================
# TABS
# ==========================================
t1, t2, t3, t4 = st.tabs(["📌 Pointi & Muhtasari", "❓ Uliza", "🧮 Hesabu", "🎯 Mazoezi"])

# ---- 1. POINTI MUHIMU & MUHTASARI ----
with t1:
    topic = st.text_input("Maada / mada (si lazima):", placeholder="Mfano: Appendicitis, Pre-eclampsia, Pneumonia kwa watoto")
    mode = st.selectbox(
        "Unataka nini?",
        [
            "Muhtasari wa pamoja (unganisha rejea zote)",
            "Pointi muhimu kutoka kila rejea",
            "Linganisha rejea (mfanano na tofauti)",
            "Notisi za mtihani (pointi za haraka + mnemonics)",
        ],
    )
    if st.button("✨ Chambua", key="b1"):
        if need_ready(need_refs=True):
            tasks = {
                "Muhtasari wa pamoja (unganisha rejea zote)":
                    "Unganisha pointi muhimu kutoka rejea zote kuwa muhtasari MMOJA uliopangwa vizuri kwa vichwa vidogo. "
                    "Usirudie pointi zilezile; weka chanzo kwa kila pointi muhimu.",
                "Pointi muhimu kutoka kila rejea":
                    "Kwa kila rejea, orodhesha pointi muhimu zaidi (zisizozidi 10), kisha mwishoni toa pointi zinazojirudia kwenye rejea nyingi.",
                "Linganisha rejea (mfanano na tofauti)":
                    "Linganisha rejea zote: wapi zinakubaliana, wapi zinatofautiana (dozi, vigezo, uainishaji), na ipi ya kuamini zaidi kwa nini.",
                "Notisi za mtihani (pointi za haraka + mnemonics)":
                    "Tengeneza notisi fupi za kukariri kwa mtihani: pointi za haraka, mnemonics, na 'pointi zinazoulizwa mara nyingi'.",
            }
            prompt = f"Maada: {topic or 'zote zilizo kwenye rejea'}.\n{tasks[mode]}"
            run("r1", prompt, strict=True, use_refs=True)
    show("r1", "muhtasari.md")

# ---- 2. ULIZA ----
with t2:
    q = st.text_area("Andika swali lako:", placeholder="Mfano: Eleza hatua za management ya severe pre-eclampsia")
    strict = st.checkbox("Tumia rejea zangu pekee (usahihi wa juu)", value=True)
    if st.button("🔎 Pata jibu", key="b2"):
        if q.strip() and need_ready(need_refs=strict):
            run("r2", q, strict=strict, use_refs=bool(st.session_state["refs"]))
        elif not q.strip():
            st.warning("Andika swali kwanza.")
    show("r2", "jibu.md")

# ---- 3. HESABU ----
with t3:
    st.caption("Hesabu hufanywa kwa kuendesha code halisi (si makadirio ya AI), kwa usahihi zaidi.")
    mq = st.text_area(
        "Andika swali la hesabu:",
        placeholder="Mfano: Mtoto wa kilo 12 anahitaji paracetamol 15 mg/kg. Syrup ni 120 mg/5 mL. Dozi ni mL ngapi?",
    )
    if st.button("🧮 Tatua", key="b3"):
        if mq.strip() and need_ready(need_refs=False):
            prompt = (
                f"{mq}\n\nTatua hatua kwa hatua, onyesha fomula, vitengo (units) na jibu la mwisho. "
                "Tumia code kuhesabu. Hakiki jibu mara ya pili. "
                "Ikiwa ni dozi ya dawa, kumbusha kuhakiki na STG/mfamasia."
            )
            run("r3", prompt, strict=False, use_refs=False, code_exec=True, temperature=0.0)
        elif not mq.strip():
            st.warning("Andika swali kwanza.")
    show("r3", "hesabu.md")

# ---- 4. MAZOEZI ----
with t4:
    ptopic = st.text_input("Maada ya mazoezi:", placeholder="Mfano: Management ya burns", key="pt")
    kind = st.selectbox("Aina:", ["MCQ (chaguo nne)", "Flashcards (swali/jibu)", "SAQ (maswali mafupi)", "Kesi ya kitabibu (vignette) na maswali"])
    n = st.slider("Idadi:", 3, 15, 5)
    level = st.select_slider("Ugumu:", ["Rahisi", "Wastani", "Ngumu"], value="Wastani")
    use_refs_p = st.checkbox("Tumia rejea zangu", value=bool(st.session_state["refs"]))
    if st.button("🎯 Tengeneza", key="b4"):
        if need_ready(need_refs=use_refs_p):
            prompt = (
                f"Tengeneza {n} za aina: {kind}. Maada: {ptopic or 'zote zilizo kwenye rejea'}. Ugumu: {level}.\n"
                "Kwa kila swali toa jibu sahihi na maelezo mafupi ya kwa nini. "
                "Weka majibu yote mwishoni mwa orodha chini ya kichwa 'Majibu'."
            )
            run("r4", prompt, strict=use_refs_p, use_refs=use_refs_p, temperature=0.4)
    show("r4", "mazoezi.md")
