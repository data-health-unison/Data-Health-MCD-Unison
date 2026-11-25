# Cómo contribuir

Convenciones del equipo para ramas, commits y pull requests. El flujo para proponer y descargar una fuente
nueva está en [docs/workflow.md](docs/workflow.md).

## Ramas

Toda rama sale de `main` actualizado y se nombra `tipo/descripcion-corta`: minúsculas, palabras separadas
por guiones, sin acentos ni ñ.

```bash
git switch main
git pull --ff-only
git switch -c feat/procesar-conapo-marg-001
```

| Tipo        | Para qué                                                        | Ejemplo                          |
|-------------|-----------------------------------------------------------------|----------------------------------|
| `feat/`     | Funcionalidad nueva: una fuente, un paso del pipeline, una vista | `feat/candidatos-de-respaldo`    |
| `fix/`      | Corrección de un error                                          | `fix/clave-municipio-sin-ceros`  |
| `docs/`     | Solo documentación: README, diccionarios, notebooks de reporte  | `docs/ficha-tecnica`             |
| `chore/`    | Mantenimiento: dependencias, lint, configuración, limpieza      | `chore/limite-sakbe-y-lint`      |
| `refactor/` | Reorganizar código sin cambiar resultados                       | `refactor/lectura-de-fuentes`    |
| `exp/`      | Análisis exploratorio o experimento que aún no se aprueba       | `exp/indice-marginacion`         |

La etapa del pipeline (ingesta, procesamiento, EDA) va en la descripción, no en el prefijo:
`feat/procesar-inegi-pop-001`, no `processing/inegi-pop-001`.

Una rama `exp/` puede no fusionarse nunca. Si el experimento se aprueba, se fusiona como cualquier otra; si no,
se cierra su PR y se borra.

## Commits

Formato `tipo: descripción`, en español y en minúsculas, con los mismos tipos de las ramas (`feat`, `fix`,
`docs`, `chore`, `refactor`, `exp`). La descripción dice qué cambia, no cómo se hizo.

```text
feat: respaldo con CONEVAL para localidades sin ruta
fix: coordenadas de 12 establecimientos fuera de operación
docs: cifras actualizadas tras el ruteo final
```

- Un commit por cambio coherente: no mezclar una corrección con una funcionalidad nueva.
- Si hace falta explicar el porqué, va en el cuerpo del mensaje, separado del título por una línea vacía.
- Nunca se suben datos (`data/`), el archivo `.env` ni las llaves o tokens. `.gitignore` ya los excluye.

## Pull requests

Todo cambio entra a `main` por pull request; nadie sube commits directo a `main`.

1. Antes de abrirlo, `make test` y `make lint` deben pasar.
2. El título sigue el formato de los commits: `feat: candidatos de respaldo cuando SAKBÉ no ubica a un
   establecimiento`.
3. La descripción dice qué cambia, por qué y cómo se probó. Si el cambio mueve resultados (cifras del README,
   tabla final, figuras), se anotan las cifras antes y después.
4. Lo revisa al menos un integrante que no sea el autor. El autor no aprueba su propio PR.
5. Se fusiona con *Create a merge commit*, para conservar la historia de la rama.

## Actualizar una rama con `main`

Si `main` avanzó mientras se trabajaba, se trae con merge, no con rebase: rebase reescribe la historia y
rompe la copia de quien ya tenga la rama.

```bash
git switch main
git pull --ff-only
git switch feat/mi-rama
git merge main -m "merge: main en feat/mi-rama"
```

Los conflictos se resuelven en la rama, nunca en `main`.

## Después de fusionar

Quien fusiona el PR borra la rama a mano:

1. En GitHub, con el botón *Delete branch* que aparece en el PR ya fusionado.
2. En su copia local:

   ```bash
   git switch main
   git pull --ff-only
   git branch -d feat/mi-rama
   git fetch --prune
   ```

`git branch -d` se niega a borrar una rama que no esté fusionada, así que no se pierde trabajo por accidente.
Los demás integrantes borran su copia local con los mismos dos últimos comandos.
