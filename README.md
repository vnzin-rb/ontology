# Ontology

Ferramenta de linha de comando para validar e explorar ontologias pequenas em JSON. O código usa a biblioteca padrão do Python.

## Primeiros passos

```sh
python ontology.py validate examples/library.json examples/transit.json
python ontology.py summary examples/transit.json
python ontology.py ancestors examples/transit.json Station
python ontology.py descendants examples/transit.json Stop
python ontology.py relations examples/library.json Book
python ontology.py instances examples/transit.json Stop --include-descendants
python ontology.py export-dot examples/library.json > library.dot
python ontology.py export-dot examples/transit.json --include-instances > transit.dot
python ontology.py diff examples/library.json examples/transit.json
```

A validação retorna código 1 quando algum arquivo tem erro e código 0 quando todos são válidos. Use `validate --format json` para obter diagnóstico estruturado em scripts.

O comando `instances` retorna os IDs das instâncias da classe. A opção `--include-descendants` inclui as instâncias das subclasses diretas e indiretas.

Para instalar o comando localmente, rode `python -m pip install .` e use `ontology` no lugar de `python ontology.py`.

## Formato

| Campo | Conteúdo |
| --- | --- |
| `classes` | Lista obrigatória com `id`, `label` e `parents` opcional. |
| `relations` | Lista opcional com `id`, `source` e `target`. |
| `instances` | Lista opcional com `id`, `class` e `label` opcional. |

Cada identificador é único dentro da sua lista. As referências apontam para classes existentes e a herança é acíclica. Use [ontology.schema.json](ontology.schema.json) para validar a estrutura no editor.
Cada chave de um objeto JSON pode aparecer uma única vez dentro desse objeto.

```sh
python -m unittest discover -s tests
```
