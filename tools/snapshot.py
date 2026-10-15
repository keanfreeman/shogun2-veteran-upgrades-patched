"""Record the game data a build reads, and replay it without the game (e.g. in a cloud session).

    python tools/snapshot.py record SNAPDIR -- path/to/script.py [args...]
    python tools/snapshot.py replay SNAPDIR -- path/to/script.py [args...]

The mod builds read game data in three ways, all hooked here, for paths inside the game's data folder
or RPFM's schema only (everything else - e.g. reading the pack a build just wrote - passes through):
  * tools_packread.read_index(pack) / extract(pack, name): pack contents (patched as the module loads,
    whichever copy of tools_packread the script imports)
  * open(): loose files such as the RPFM schema and MoSS's encyclopedia pages
  * os.path.exists(): checks for packs and folders
record runs the script against the real game and saves what it read into SNAPDIR (merging with what's
there, so several builds can share one snapshot). replay serves the same data from a virtual folder:
tools_db finds "the game" at /vu_snapshot/game and the schema at /vu_snapshot/schema/schema_sho2.ron,
neither of which exists. Anything the snapshot lacks fails loudly ("not in the snapshot: ...") - record
again on the machine with the game.

The snapshot holds excerpts of the game's and mods' data: keep it PRIVATE (never in a public repo).
"""
import builtins, gzip, hashlib, importlib.machinery, io, json, os, runpy, sys

VIRTUAL = "/vu_snapshot"
REAL_OPEN, REAL_EXISTS = builtins.open, os.path.exists


class Snapshot:
    def __init__(self, folder, mode):
        self.folder, self.mode = folder, mode
        self.meta = {"index": {}, "extract": {}, "files": {}, "exists": {}}
        path = os.path.join(folder, "snapshot.json.gz")
        if REAL_EXISTS(path):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                self.meta.update(json.load(f))
        elif mode == "replay":
            raise SystemExit(f"no snapshot in {folder}")
        self.roots = {}   # real folder or file -> virtual key prefix ("game", "schema")
        self.cache = {}   # key -> pack index, kept in memory: extract() lists the pack on every call

    # --- storage -----------------------------------------------------------------------------
    def put_blob(self, data):
        h = hashlib.sha256(data).hexdigest()
        p = os.path.join(self.folder, "blobs", h[:2], h + ".gz")
        if not REAL_EXISTS(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with gzip.open(p, "wb", compresslevel=6) as f:
                f.write(data)
        return h

    def get_blob(self, h):
        with gzip.open(os.path.join(self.folder, "blobs", h[:2], h + ".gz"), "rb") as f:
            return f.read()

    def save(self):
        os.makedirs(self.folder, exist_ok=True)
        with gzip.open(os.path.join(self.folder, "snapshot.json.gz"), "wt", encoding="utf-8") as f:
            json.dump(self.meta, f, sort_keys=True, separators=(",", ":"))

    # --- paths ---------------------------------------------------------------------------------
    def key(self, path):
        """'game/<relative path>' / 'schema' for a path in a snapshotted root, else None."""
        try:
            p = os.path.abspath(os.fspath(path))
        except TypeError:
            return None
        if self.mode == "replay":
            if p == VIRTUAL or p.startswith(VIRTUAL + os.sep):
                return os.path.relpath(p, VIRTUAL).replace(os.sep, "/")
            return None
        for root, prefix in self.roots.items():
            if p == root:
                return prefix
            if p.startswith(root + os.sep):
                return prefix + "/" + os.path.relpath(p, root).replace(os.sep, "/")
        return None

    def missing(self, what):
        raise SystemExit(f"not in the snapshot: {what} - record it again on the machine with the game "
                         "(tools/snapshot.py record ...)")

    # --- hooks ---------------------------------------------------------------------------------
    def install(self):
        snap = self

        def exists(path):
            k = snap.key(path)
            if k is None:
                return REAL_EXISTS(path)
            if snap.mode == "replay":
                if k in snap.meta["exists"]:
                    return snap.meta["exists"][k]
                # not checked while recording: exists if the snapshot holds it
                return (k in snap.meta["files"] or k in snap.meta["index"]
                        or any(e.startswith(k + "|") for e in snap.meta["extract"]))
            r = REAL_EXISTS(path)
            snap.meta["exists"][k] = r
            return r

        def open_(file, mode="r", *args, **kwargs):
            k = snap.key(file) if isinstance(file, (str, bytes, os.PathLike)) else None
            # packs are recorded by read_index/extract, file by file - never whole (gigabytes)
            if k is None or any(c in mode for c in "wax+") or k.lower().endswith(".pack"):
                return REAL_OPEN(file, mode, *args, **kwargs)
            if snap.mode == "replay":
                if k not in snap.meta["files"]:
                    snap.missing(k)
                data = snap.get_blob(snap.meta["files"][k])
            else:
                with REAL_OPEN(file, "rb") as f:
                    data = f.read()
                snap.meta["files"][k] = snap.put_blob(data)
            if "b" in mode:
                return io.BytesIO(data)
            return io.StringIO(data.decode(kwargs.get("encoding") or "utf-8"))

        builtins.open = open_
        os.path.exists = exists

        class Finder:
            """Patches tools_packread.read_index/extract as soon as the script imports it."""
            def find_spec(self, name, path=None, target=None):
                if name != "tools_packread":
                    return None
                spec = importlib.machinery.PathFinder.find_spec(name, path)
                if spec is None:
                    return None
                real_exec = spec.loader.exec_module

                def exec_module(module):
                    real_exec(module)
                    snap.patch_packread(module)
                spec.loader.exec_module = exec_module
                return spec

        sys.meta_path.insert(0, Finder())

    def patch_packread(self, module):
        snap, real_index, real_extract = self, module.read_index, module.extract

        def read_index(path):
            k = snap.key(path)
            if k is None:
                return real_index(path)
            if k in snap.cache:
                return snap.cache[k]
            if snap.mode == "replay":
                if k not in snap.meta["index"]:
                    snap.missing(f"index of {k}")
                entries = [tuple(e) for e in json.loads(snap.get_blob(snap.meta["index"][k]))]
            else:
                entries = real_index(path)
                snap.meta["index"][k] = snap.put_blob(json.dumps(entries).encode())
            snap.cache[k] = entries
            return entries

        def extract(path, name):
            k = snap.key(path)
            if k is None:
                return real_extract(path, name)
            ek = k + "|" + name.lower()
            if snap.mode == "replay":
                if ek not in snap.meta["extract"]:
                    snap.missing(f"{name} in {k}")
                return snap.get_blob(snap.meta["extract"][ek])
            data = real_extract(path, name)
            snap.meta["extract"][ek] = snap.put_blob(data)
            return data

        module.read_index, module.extract = read_index, extract


def main(argv):
    if len(argv) < 4 or argv[0] not in ("record", "replay") or "--" not in argv:
        raise SystemExit(__doc__)
    mode, folder = argv[0], os.path.abspath(argv[1])
    script_args = argv[argv.index("--") + 1:]
    snap = Snapshot(folder, mode)
    sys.path.insert(0, os.path.dirname(os.path.abspath(script_args[0])))   # as when the script runs itself
    if mode == "record":
        # where the script's tools_db will look: the same rules as tools_db itself
        game = os.environ.get("SHOGUN2_DATA") or next(
            (p for p in (os.path.expanduser("~/.local/share/Steam/steamapps/common/Total War SHOGUN 2/data"),
                         os.path.expanduser("~/.steam/steam/steamapps/common/Total War SHOGUN 2/data"),
                         r"C:\Program Files (x86)\Steam\steamapps\common\Total War SHOGUN 2\data") if REAL_EXISTS(p)), None)
        schema = os.environ.get("RPFM_SCHEMA") or next(
            (p for p in (os.path.expanduser("~/.var/app/io.github.frodo45127.rpfm/config/rpfm/schemas/schema_sho2.ron"),
                         os.path.expanduser("~/.config/rpfm/schemas/schema_sho2.ron")) if REAL_EXISTS(p)), None)
        if not game or not schema:
            raise SystemExit("record needs the game (SHOGUN2_DATA) and RPFM's schema (RPFM_SCHEMA)")
        snap.roots = {os.path.abspath(game): "game", os.path.abspath(schema): "schema/schema_sho2.ron"}
        os.environ["SHOGUN2_DATA"], os.environ["RPFM_SCHEMA"] = game, schema
    else:
        os.environ["SHOGUN2_DATA"] = VIRTUAL + "/game"
        os.environ["RPFM_SCHEMA"] = VIRTUAL + "/schema/schema_sho2.ron"
        snap.meta["exists"].setdefault("game", True)
        snap.meta["exists"].setdefault("schema/schema_sho2.ron", True)
    snap.install()
    sys.argv = script_args
    try:
        runpy.run_path(script_args[0], run_name="__main__")
    except SystemExit as e:
        if e.code not in (None, 0):
            raise
    finally:
        if mode == "record":
            snap.save()
            n = len(snap.meta["index"]) + len(snap.meta["extract"]) + len(snap.meta["files"])
            print(f"snapshot: {n} items in {folder}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
