# DoodleStory

[中文](README.zh-CN.md) | [English](README.en.md)

DoodleStory is a text-to-image story generation project. It turns a user's original text into a sequence of illustrated panels by combining story segmentation, panel prompt generation, style templates, and a style-bound image model.

## Product Shape

- Style library: CRUD for image styles, reference images, style metadata, style prompts, and the image model bound to each style.
- Style testing: generate a sample image from custom test text plus the selected style prompt, using the style's bound model.
- Generation tasks: accept the user's original text without rewriting it, bind the task to a selected style, split the story into panels, generate image prompts, then create images.
- Result handling: preview generated images, enlarge an image on click, and batch download all generated images.

## Codex Harness

This repository uses the Codex project harness from `codex-project-template`, adapted for DoodleStory.

Read these first before substantial implementation work:

- [Project Spec](docs/spec.md)
- [Progress Log](docs/progress.md)
- [Active Sprint Contract](docs/contracts/sprint-00-harness-adaptation.md)
- [Development Standards](docs/standards/)
- [Reference: Harness design: Building long-running applications with LLMs](docs/references/harness-design-long-running-apps.md)
