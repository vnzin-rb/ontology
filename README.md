# Ontology

Validador de ontologias pequenas em JSON, feito em Python 3 e com a biblioteca padrão.

```sh
python ontology.py validate examples/library.json
python -m unittest discover -s tests
```

Cada classe tem um identificador único, um rótulo e uma lista opcional de classes-pai. Uma relação tem identificador único e aponta para classes conhecidas nos campos `source` e `target`. A hierarquia de classes deve ser acíclica.

O comando retorna código 0 para documentos válidos e 1 para erros. As mensagens indicam o caminho do campo no JSON.
