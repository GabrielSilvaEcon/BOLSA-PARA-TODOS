"""O que a pessoa equipou na Loja Ticker, pronto para as telas usarem (Fase 8). Lê uma vez e guarda na sessão por 2 minutos
(a compra e o botão Usar/Tirar limpam o guardado). Só vale item que a conta AINDA possui (compra estornada some do visual).
Nunca levanta erro: sem login, sem banco ou com falha de leitura devolve "nada equipado" e o app fica com o visual original."""
from __future__ import annotations

import time

import streamlit as st

import loja_catalogo as LC
import visual_loja as VL

_TTL = 120


def invalidar() -> None:
    st.session_state.pop("_lj_ap", None)


def atual() -> dict:
    """{tipo: {**efeito, "id", "nome"}} só com o que está equipado e possuído. Ex.: atual().get("moldura")."""
    try:
        c = st.session_state.get("_lj_ap")
        if c and time.time() - c[0] < _TTL:
            return c[1]
        import tickercoins as TC
        import usuarios
        u = usuarios.usuario()
        out: dict = {}
        if u:
            eq = TC.equipado(u["email"])
            pos = {b["produto_id"] for b in TC.beneficios_ativos(u["id"])}
            for kind in LC.equipaveis():
                p = LC.POR_ID.get(eq.get(kind))
                if p and p["id"] in pos and p["efeito"]["kind"] == kind:
                    out[kind] = {**p["efeito"], "id": p["id"], "nome": p["nome"]}
        st.session_state["_lj_ap"] = (time.time(), out)
        return out
    except Exception:
        return {}


def efeito(tipo: str) -> dict | None:
    return atual().get(tipo)


def css_do_tema() -> str:
    """<style> do tema equipado ('' se não há). Vai logo depois dos CSS globais do app."""
    t = atual().get("tema")
    return VL.css_tema(LC.PALETAS.get(t.get("paleta")) and {**LC.PALETAS[t["paleta"]], "luz": t.get("luz")}) if t else ""
