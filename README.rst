Installing with Pip
-------------------

Ensure that you have libxml2 installed, and run:

.. code-block:: sh

   python3 -m pip install mut

Automatic Installation (Old)
----------------------------

Mut provides an automatic installation script requiring only ``bash`` and
``curl``, supporting the following platforms:

.. list-table::

   * - OSX
     - Requires `Brew <http://brew.sh/>`_
   * - Debian/Ubuntu
     -

The automatic installation script can configure ``bash`` and ``zsh`` shells.

.. code-block:: sh

   bash -c "$(curl -fsSL https://raw.githubusercontent.com/mongodb/mut/master/install.sh)"
