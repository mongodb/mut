Installing with Pip
-------------------

Ensure that you have libxml2 installed, and run:

.. code-block:: sh

   python3 -m pip install mut

Publishing a Release
--------------------

A sample version number is used in these instructions. Ensure that you
change it appropriately when running these commands.

* First, ensure that you have the dependencies installed:

  .. code-block:: sh

     python3 -m pip install pycodestyle mypy twine

* Ensure that you have created a PyPi account, and stored your API key in ``.pypirc``:

  https://packaging.python.org/guides/distributing-packages-using-setuptools/#create-an-account

* Run the linter, and ensure that everything looks good:

  .. code-block:: sh

     ./lint.sh

* Bump the version in ``mut/__init__.py``. For example, if it reads ``0.6.9.dev0``,
  you might change it to ``0.6.10`` or ``0.7.0``. Commit that, and tag the release:

  .. code-block:: sh

     git add mut/__init__.py
     git commit -m "Bump to 0.6.10"
     git tag -s v0.6.10

* Publish the release to PyPi:

  .. code-block:: sh

     git clean -xfd
     python3 setup.py sdist bdist_wheel
     python3 -m twine upload --repository pypi dist/*

* Now make a post-release bump, and add ``.dev0`` to the version number in ``mut/__init__.py``,
  for example ``0.6.10.dev0``. Then commit that, and push everything:

  .. code-block:: sh

     git add mut/__init__.py
     git commit -m "Post-release bump"
     git push origin master
     git push --tags
