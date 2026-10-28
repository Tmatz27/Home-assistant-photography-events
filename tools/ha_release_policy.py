"""Release arguments only; importing/testing this module never publishes anything."""
import re


def release_arguments(version,commit):
    match=re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-dev\.[1-9]\d*)?',version)
    if not match or not re.fullmatch('[0-9a-f]{40}',commit):
        raise ValueError('Exact version and commit required')
    args=['gh','release','create','v'+version,'custom_components/photography_events/www/photography-events-card.js',
        '--target',commit,'--title','Photography Events v'+version,'--notes-file','release-notes.md']
    return args+(['--prerelease','--latest=false'] if match.group(4) else ['--latest'])


if __name__=='__main__':
    import argparse
    import subprocess
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',required=True)
    parser.add_argument('--commit',required=True)
    args=parser.parse_args()
    subprocess.run(release_arguments(args.version,args.commit),check=True)
