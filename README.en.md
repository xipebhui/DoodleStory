# DoodleStory

[中文](README.zh-CN.md) | [English](README.en.md)

DoodleStory is a text-to-image story generation project. It converts a user's original story into illustrated image panels through story segmentation, panel prompt generation, style templates, and style-bound image models.

## Product Shape

- Style library: CRUD for styles, reference images, metadata, style prompts, and image model bindings.
- Style testing: generate a sample image from custom test text combined with the style prompt.
- Generation tasks: keep the user's original text unchanged, bind it to a style, split it into panels, generate image prompts, and render images.
- Result handling: enlarged image preview and batch download for all generated images.

## Codex Harness

This repository uses the Codex project harness from `codex-project-template`, adapted for DoodleStory.

Read these first before substantial implementation work:

- [Project Spec](docs/spec.md)
- [Progress Log](docs/progress.md)
- [Active Sprint Contract](docs/contracts/sprint-01-product-design.md)
- [Product Design](docs/design/README.md)
- [Development Standards](docs/standards/)
- [Reference: Harness design: Building long-running applications with LLMs](docs/references/harness-design-long-running-apps.md)
