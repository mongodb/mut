# `mut`

https://github.com/mongodb/mut
Copyright 2023 MongoDB Inc.

`mut` provides a handful of tools used in MongoDB's documentation platform.

* `mut-index` turns snooty-parser-generated abstract syntax trees into manifests
  that can be ingested into Atlas Search to power the docs' search.
* `mut-redirects` generates redirects from our bespoke redirect definition format,
  making it "easy" to ensure that readers never find themselves on a 404ing page
  when swapping versions or following old links
* `mut-images` turns SVGs into PNGs I think?
* `mut-stage` uploads files to S3 with minimal fuss for the user

`mut` is licensed under the Apache License, Version 2.0. 
See the `LICENSE` file for details.

## Installation

### Legacy mut (v0.9 and earlier)

`mut v0.9.x` exists to support the needs of MongoDB docs properties building with the legacy (giza)
toolchain. To use `mut`, you need python3, along with a bunch of other dependencies.
To install `mut` for use with giza, follow the instructions on the writer setup wiki.

### Modern `mut` (v0.10 and later)

To use mut locally, you need python 3.8 or later.

As of v0.10, each `mut` release builds with `poetry`. 
If you do *not* have `poetry` installed, install it following 
[their excellent instructions](https://python-poetry.org/docs/).
You should probably also `python3 -m pip install wheel` if you haven't.

1. Check out the tag you want to build:

```shell
git checkout <tag>
```

2. Build a wheel using `poetry build`.

> [!NOTE]
> You may need to add read privaleges to your *Users/\<your-username>/.pyenv/* folder.

```shell
poetry install # to make sure everything's set up
poetry build   # to actually build it
```

3. Use `pip` to install the newly-generated `mut` wheel:

```shell
python3 -m pip install dist/whatever.whl
```

Alternatively, from v0.10.3, we offer a pre-built `mut` bundle that includes
*all the things* so you need simply unzip the bundle and run the executable.
At present it only does this for Linux, though we'll probably change that at some point.

## Developing `mut`

To develop `mut` locally, ensure you have `poetry` installed by running `which poetry`.
If you do *not* have `poetry` installed, install it following 
[their excellent instructions](https://python-poetry.org/docs/).

1. Set up the project's dependencies.
   
   ```
   poetry install
   ```

2. Make your changes to the source code.

3. Run `make test` and `make format` to check that the tests pass 
   and fix your formatting.

4. Active a shell where the `mut` commands you just built are available:

   ```
   poetry shell
   ```

5. When you're done testing, terminate your shell by running:

   ```
   exit
   ```

## Releasing `mut`

### Do it the easy way

From the [releases page](https://github.com/mongodb/mut/releases), click "Draft a new release".
Create a new tag in the tag dropdown, fill ou the release name and description, generate
the changelog using the handy changelog generation button, and click "Publish release".

Creating the tag will [run the release workflow](https://github.com/mongodb/mut/blob/master/.github/workflows/release.yml),
building the stuff and (potentially ?) creating an extra draft release which you can then delete.

Finally, update the version number in pyproject.toml.

### Generate the tag manually because you like commandline git

If you're the sort of person who likes making your tags manually (like Allison): 

1. First, update the version number in pyproject.toml.

2. Create a tag and push it to master:

   ```shell
   git tag v0.10.3
   git push origin master --tags
   ```

   Creating the tag will [run the release workflow](https://github.com/mongodb/mut/blob/master/.github/workflows/release.yml),
   building the stuff and creating a draft release on the [releases page](https://github.com/mongodb/mut/releases).

3. Go to the releases page, find the newly-created release draft and fill out the
   release description, generate release notes, etc.

