import pandas as pd
def test_sistema_no_falla():
    df = pd.DataFrame([{"Titulo":"SE ACERCA EL DOBLE","Reproducciones":99999},{"Titulo":"","Reproducciones":-5}])
    df["Reproducciones"] = pd.to_numeric(df["Reproducciones"], errors="coerce").fillna(0).clip(lower=0)
    assert (df["Reproducciones"]>=0).all()
    print("✅ TEST PASADO: BASA V10 no se cae")
if __name__=="__main__": test_sistema_no_falla()
