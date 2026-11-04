from pathlib import Path
import os,subprocess,sys
B=Path(__file__).resolve().parents[1];tmp=Path('/tmp/svec-chain');tmp.mkdir(exist_ok=True)
s=(B/'01-source-code/svec_chain.js').read_text().replace("server.listen(port,'127.0.0.1')","server.listen(port,'0.0.0.0')")
s=s.replace("const contract=await new ethers.ContractFactory", "fs.writeFileSync(path.join(root,'compiler_artifact.json'),JSON.stringify({abi:art.abi,creationBytecode:art.evm.bytecode.object,solc:solc.version()},null,2));\n const contract=await new ethers.ContractFactory",1)
s=s.replace("const codeSha256=sha(ethers.getBytes(await provider.getCode(address)));", "const deployedCode=await provider.getCode(address);fs.writeFileSync(path.join(root,'deployed_code.hex'),deployedCode);const codeSha256=sha(ethers.getBytes(deployedCode));")
(tmp/'svec_chain.js').write_text(s);(tmp/'CommitmentRegistry.sol').write_bytes((B/'02-smart-contract/CommitmentRegistry.sol').read_bytes())
raise SystemExit(subprocess.call(['node',str(tmp/'svec_chain.js'),'/state/fixture','19880']))
