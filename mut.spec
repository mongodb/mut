import os.path


def make_program(filename: str):
    block_cipher = None

    a = Analysis(
        [filename],
        pathex=[],
        binaries=[],
        datas=[],
        hiddenimports=[],
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=[],
        win_no_prefer_redirects=False,
        win_private_assemblies=False,
        cipher=block_cipher,
        noarchive=False,
    )
    pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=os.path.splitext(filename)[0],
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

    return (a, pyz, exe)

mut_index_a, mut_index_pyz, mut_index_exe = make_program("mut-index.py")
mut_publish_a, mut_publish_pyz, mut_publish_exe = make_program("mut-publish.py")
mut_redirects_a, mut_redirects_pyz, mut_redirects_exe = make_program("mut-redirects.py")


coll = COLLECT(mut_index_exe,
               mut_index_a.binaries,
               mut_index_a.zipfiles,
               mut_index_a.datas,

               mut_publish_exe,
               mut_publish_a.binaries,
               mut_publish_a.zipfiles,
               mut_publish_a.datas,

               mut_redirects_exe,
               mut_redirects_a.binaries,
               mut_redirects_a.zipfiles,
               mut_redirects_a.datas,

               name='mut')
