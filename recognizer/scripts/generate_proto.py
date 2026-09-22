"""Regenerate Python protocol bindings from the repository's single .proto."""
from pathlib import Path
import sys

def main():
    from grpc_tools import protoc
    root=Path(__file__).resolve().parents[2]
    output=root/"recognizer/star_recognizer/generated"
    output.mkdir(parents=True,exist_ok=True)
    result=protoc.main(["grpc_tools.protoc","-I"+str(root/"proto"),"--python_out="+str(output),
                       "--grpc_python_out="+str(output),str(root/"proto/star/v1/star.proto")])
    if result:
        return result
    for folder in (output,output/"star",output/"star/v1"):
        (folder/"__init__.py").touch()
    stub=output/"star/v1/star_pb2_grpc.py"
    content=stub.read_text()
    content=content.replace("from star.v1 import star_pb2", "from star_recognizer.generated.star.v1 import star_pb2")
    stub.write_text(content)
    print("Generated Python bindings from proto/star/v1/star.proto")
    return 0

if __name__=="__main__":
    sys.exit(main())
