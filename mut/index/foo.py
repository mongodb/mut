from pathlib import Path
from bson import decode_all
from json import loads, dumps

ROOT_PATH = Path("/Users/allison/snooty/mut/mut/test_data_index/documents")


data = decode_all(ROOT_PATH.joinpath(Path("code-example.bson")).read_bytes())

print(dumps(data))
exit()




# ..children[type != directive].children[type=paragraph]