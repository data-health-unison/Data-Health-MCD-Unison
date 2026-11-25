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
4. El PR agrega su línea en la sección **Sin publicar** de [CHANGELOG.md](CHANGELOG.md), en el apartado que le
   toca (*Agregado*, *Cambiado*, *Corregido* o *Eliminado*). Los cambios que no se notan fuera del código
   (lint, pruebas internas) no necesitan línea.
5. Lo revisa al menos un integrante que no sea el autor. El autor no aprueba su propio PR.
6. Se fusiona con *Create a merge commit*, para conservar la historia de la rama.

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

## Versiones

El proyecto usa [versionado semántico](https://semver.org/lang/es/) (`MAYOR.MENOR.PARCHE`), adaptado a un proyecto
de datos: el número que sube depende de si las cifras siguen siendo comparables con las de la versión anterior.

| Sube | Cuándo | Ejemplo |
|---|---|---|
| MAYOR (`1.0.0` → `2.0.0`) | Cambia la metodología y las cifras dejan de ser comparables | Otro umbral de tiempo, otra definición de establecimiento operativo, columnas de la tabla final que se quitan o renombran |
| MENOR (`0.2.0` → `0.3.0`) | Se agrega algo y lo anterior sigue siendo comparable | Una fuente nueva, un indicador nuevo, una vista nueva del tablero |
| PARCHE (`0.2.0` → `0.2.1`) | Corrección que no cambia la metodología | Un error en el código, la coordenada de un establecimiento, documentación |

Mientras la versión empiece con `0.`, la metodología sigue en construcción. La `1.0.0` es la entrega final del
proyecto.

La versión vive solo en `src/health_data/__init__.py` (`__version__`); `pyproject.toml` y el tablero la leen de
ahí.

### Cuándo se publica una versión

En cada hito (entregas del curso, presentaciones) y siempre que cambien las cifras publicadas. No en cada PR.

### Cómo se publica

1. En una rama `chore/version-X.Y.Z`:
   - En `CHANGELOG.md`, lo que está en **Sin publicar** pasa a una sección `## [X.Y.Z] - AAAA-MM-DD`, y se
     actualizan los enlaces del final.
   - Si las cifras cambiaron, la sección lleva las nuevas.
   - `__version__` sube a `X.Y.Z` en `src/health_data/__init__.py`.
   - Con esos cambios ya en un commit, se corre `make reprocesar` para que todo lo procesado y el manifiesto
     registren ese commit sin cambios pendientes, y el manifiesto se copia a git:
     `cp data/processed/manifiesto.json reports/manifiestos/vX.Y.Z.json`. Así las cifras de la versión quedan
     ligadas a las huellas exactas de sus entradas y salidas.
   - Si el caché de SAKBÉ cambió desde el último respaldo (el manifiesto lo avisa), `make respaldo-sakbe` y
     subir el archivo a la carpeta compartida.
2. Se abre el PR, se revisa y se fusiona como cualquier otro.
3. En `main` ya actualizado se crea el tag y se sube:

   ```bash
   git switch main
   git pull --ff-only
   git tag -a vX.Y.Z -m "vX.Y.Z: resumen en una línea"
   git push origin vX.Y.Z
   ```

4. Opcional: en GitHub, *Releases* → *Draft a new release* con ese tag y el texto de su sección del CHANGELOG.

Un tag no se mueve ni se borra una vez publicado. Si la versión salió con un error, se corrige en la siguiente.
