"""Upload original music artwork and browser previews to the authorized HF dataset.

Original bytes are preserved. Generated images and upload receipts stay ignored
under local/. Only a JSON manifest is written to the GitHub source tree.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageOps
from huggingface_hub import HfApi
from build_music_atlas import ROOT, edge_color

REPO='edzee3000/GithubData'
PREFIX='homepage-assets/music/atlas'


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def upload(archive, repo=REPO, prefix=PREFIX):
    archive=Path(archive).resolve()
    source=json.loads((archive/'manifest.json').read_text(encoding='utf8'))['assets']
    raw=json.loads((ROOT/'_data/music.json').read_text(encoding='utf8'))
    wanted={s['album']['picUrl'] for s in raw if s['album'].get('picUrl')}
    missing=wanted-set(source)
    if missing:raise ValueError(f'{len(missing)} source covers missing from archive')
    api=HfApi()
    if api.whoami()['name']!=repo.split('/')[0]:raise ValueError('Unexpected HF account')
    stage=(ROOT/'local/music-atlas/hf-artwork').resolve()
    stage.mkdir(parents=True,exist_ok=True)
    (stage/'previews').mkdir(exist_ok=True);(stage/'small').mkdir(exist_ok=True)
    assets={};original_names=[]
    for url in sorted(wanted):
        original=archive/source[url]['file']
        checksum=digest(original)
        if checksum!=source[url]['sha256']:raise ValueError('Original hash mismatch: '+original.name)
        name=original.stem+'.jpg';original_names.append(original.name)
        with Image.open(original) as im:
            width,height=im.size
            for folder,size,quality in [('previews',512,92),('small',64,85)]:
                target=stage/folder/name
                if not target.exists():
                    ImageOps.pad(im.convert('RGB'),(size,size),method=Image.Resampling.LANCZOS,
                        color='#182019').save(target,quality=quality,optimize=True)
        with Image.open(stage/'previews'/name) as preview:
            color=edge_color(preview.resize((192,192),Image.Resampling.LANCZOS))
        assets[url]=dict(original=f'{prefix}/originals/{original.name}',
            preview=f'{prefix}/previews/{name}',small=f'{prefix}/small/{name}',
            sha256=checksum,bytes=original.stat().st_size,width=width,height=height,edgeColor=color)
    print(f'Prepared {len(assets)} untouched originals and two preview sizes',flush=True)
    receipt=stage/'receipt.json'
    done=json.loads(receipt.read_text(encoding='utf8')) if receipt.exists() else {}
    for label,folder,path,allow in [
        ('originals',archive/'covers',prefix+'/originals',original_names),
        ('previews',stage/'previews',prefix+'/previews',['*.jpg']),
        ('small',stage/'small',prefix+'/small',['*.jpg'])]:
        # HF upload_folder is content-addressed and safely reuses uploaded bytes.
        print('Uploading '+label,flush=True)
        commit=api.upload_folder(repo_id=repo,repo_type='dataset',folder_path=str(folder),
            path_in_repo=path,allow_patterns=allow,
            commit_message=f'Host Music atlas {label} ({len(assets)} album covers)')
        done[label]=commit.oid;receipt.write_text(json.dumps(done,indent=2),encoding='utf8')
    revision=done['small']
    paths=[entry[key] for entry in assets.values() for key in ['original','preview','small']]
    seen={}
    for offset in range(0,len(paths),100):
        for item in api.get_paths_info(repo,paths[offset:offset+100],repo_type='dataset',revision=revision):
            seen[item.path]=item
    if set(paths)!=set(seen):raise ValueError('Remote upload is incomplete')
    for url,entry in assets.items():
        item=seen[entry['original']]
        if item.size!=entry['bytes']:raise ValueError('Remote original size mismatch')
        if item.lfs and item.lfs.sha256!=entry['sha256']:raise ValueError('Remote original SHA256 mismatch')
        if not item.lfs:
            original=archive/source[url]['file']
            value=hashlib.sha1(b'blob '+str(entry['bytes']).encode()+b'\0'+original.read_bytes()).hexdigest()
            if item.blob_id!=value:raise ValueError('Remote original Git blob hash mismatch')
    manifest=dict(repo=repo,revision=revision,prefix=prefix,originalCount=len(assets),
        verifiedFiles=len(seen),originalBytes=sum(e['bytes'] for e in assets.values()),assets=assets)
    (ROOT/'_data/music_artwork.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='assets'}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',default=str(ROOT.parent/'music-artwork'))
    args=parser.parse_args();upload(args.archive)
