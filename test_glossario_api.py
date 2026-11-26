"""Glossário completo no app (rota /ajuda/glossario/completo): mesmos termos da tela do Streamlit, com os 3 níveis nos termos do glossário central."""
import json

from test_social_api import dois  # noqa: F401  (fixture: duas contas logadas)


def test_glossario_completo(dois):
    ana, _ = dois
    antigo = ana.get("/ajuda/glossario").json()["termos"]
    r = ana.get("/ajuda/glossario/completo")
    assert r.status_code == 200
    t = r.json()["termos"]
    assert len(t) > len(antigo) >= 40                                   # a rota nova traz o glossário central e os indicadores além dos 44 antigos
    por_nome = {x["termo"]: x for x in t}
    pl = next(x for x in t if x.get("central") and x["central"]["pt"].startswith("Preço sobre Lucro"))
    assert set(pl["central"]["niveis"]) == {"iniciante", "intermediario", "avancado"}
    assert all(l["r"] and l["t"] for n in pl["central"]["niveis"].values() for l in n)
    assert "Ações brasileiras" in pl["central"]["classes"] and "P/E" in pl["central"]["alias"]
    assert all(x["termo"] and x["definicao"] for x in t)                # nenhum termo vazio
    assert len(por_nome) == len(t)                                      # sem termo repetido
    assert len(json.dumps(t, ensure_ascii=False)) < 400_000             # cabe numa chamada só (medido ~ metade disso)
    from fastapi.testclient import TestClient

    import api.main as API
    assert TestClient(API.app).get("/ajuda/glossario/completo").status_code == 401
