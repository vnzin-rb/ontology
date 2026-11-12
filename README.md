# Ontology

Ferramenta de linha de comando para validar e explorar ontologias pequenas em JSON. O código usa a biblioteca padrão do Python.

## Primeiros passos

```sh
python ontology.py validate examples/library.json examples/transit.json
python ontology.py summary examples/transit.json
python ontology.py ancestors examples/transit.json Station
python ontology.py relations examples/library.json Book
python ontology.py export-dot examples/library.json > library.dot
python ontology.py diff examples/library.json examples/transit.json
```

A validação retorna código 1 quando algum arquivo tem erro e código 0 quando todos são válidos. Use `validate --format json` para obter diagnóstico estruturado em scripts.

Para instalar o comando localmente, rode `python -m pip install .` e use `ontology` no lugar de `python ontology.py`.

## Formato

| Campo | Conteúdo |
| --- | --- |
| `classes` | Lista obrigatória com `id`, `label` e `parents` opcional. |
| `relations` | Lista opcional com `id`, `source` e `target`. |
| `instances` | Lista opcional com `id`, `class` e `label` opcional. |

Cada identificador é único dentro da sua lista. As referências apontam para classes existentes e a herança é acíclica. Use [ontology.schema.json](ontology.schema.json) para validar a estrutura no editor.

```sh
python -m unittest discover -s tests
```
