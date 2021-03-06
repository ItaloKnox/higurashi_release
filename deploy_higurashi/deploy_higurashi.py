import os
import shutil
import subprocess
import sys
import argparse
from sys import argv, exit, stdout
from typing import List

def isWindows():
    return sys.platform == "win32"


def call(args, **kwargs):
    print("running: {}".format(args))
    retcode = subprocess.call(args, shell=isWindows(), **kwargs)  # use shell on windows
    if retcode != 0:
        raise SystemExit(retcode)


def tryRemoveTree(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except FileNotFoundError:
        pass


def sevenZipMakeArchive(input_path, output_filename):
    tryRemoveTree(output_filename)
    call(["7z", "a", output_filename, input_path])


def sevenZipExtract(input_path, outputDir=None):
    args = ["7z", "x", input_path, '-y']
    if outputDir:
        args.append('-o' + outputDir)

    call(args)


def download(url):
    print(f"Starting download of URL: {url}")
    call(['curl', '-OJL', url])


class ChapterInfo:
    def __init__(self, name, episodeNumber, uiFileName):
        self.name = name
        self.episodeNumber = episodeNumber
        self.dataFolderName = f'HigurashiEp{episodeNumber:02}_Data'
        self.uiArchiveName = uiFileName


def compileScripts(chapter: ChapterInfo):
    """
    Compiles scripts for the given chapter.

    Expects:
        - to run on a Windows machine
        - Windows, Steam UI files
        - Windows, Steam base assets
    """
    extractKey = os.environ.get('EXTRACT_KEY')
    if extractKey is None:
        raise SystemExit("Error: Can't compile scripts as environment variable 'EXTRACT_KEY' not set.")

    baseArchiveName = f'{chapter.name}_base.7z'

    # - Download and extract the base archive for the selected game, using key
    download(f'https://07th-mod.com/misc/script_building/{baseArchiveName}')
    # Do not replace the below call with sevenZipExtract() as it would expose the 'EXTRACT_KEY'
    subprocess.call(["7z", "x", baseArchiveName, '-y', f"-p{extractKey}"], shell=isWindows())

    print(f"\n\n>> Compiling [{chapter.name}] scripts...")
    baseFolderName = f'{chapter.name}_base'

    # - Download and extract the UI archive for the selected game
    uiArchiveName = chapter.uiArchiveName
    download(f'https://07th-mod.com/rikachama/ui/{uiArchiveName}')
    sevenZipExtract(uiArchiveName, baseFolderName)

    # - Download the DLL for the selected game
    # TODO: when experimental DLL is released, don't use experimental DLL for building
    dllArchiveName = f'experimental-drojf-dll-ep{chapter.episodeNumber}.7z'
    download(f'https://github.com/drojf/higurashi-assembly/releases/latest/download/{dllArchiveName}')
    sevenZipExtract(dllArchiveName, baseFolderName)

    # - Copy the Update folder containing the scripts to be compiled to the base folder, so the game can find it
    shutil.copytree(f'Update', f'{baseFolderName}/{chapter.dataFolderName}/StreamingAssets/Update', dirs_exist_ok=True)

    # - Remove status file if it exists
    statusFilename = "higu_script_compile_status.txt"
    if os.path.exists(statusFilename):
        os.remove(statusFilename)

    # - Run the game with 'quitaftercompile' as argument
    call([f'{baseFolderName}\\HigurashiEp{chapter.episodeNumber:02}.exe', 'quitaftercompile'])

    # - Check compile status file
    if not os.path.exists(statusFilename):
        raise SystemExit("Script Compile Failed: Script compilation status file not found")

    with open(statusFilename, "r") as f:
        status = f.read().strip()
        if status != "Compile OK":
            raise SystemExit(f"Script Compile Failed: Script compilation status indicated status {status}")

    os.remove(statusFilename)

    # - Copy the CompiledUpdateScripts folder to the expected final build dir
    shutil.copytree(f'{baseFolderName}/{chapter.dataFolderName}/StreamingAssets/CompiledUpdateScripts', f'temp/{chapter.dataFolderName}/StreamingAssets/CompiledUpdateScripts', dirs_exist_ok=True)

    # Clean up
    os.remove(uiArchiveName)
    os.remove(dllArchiveName)
    shutil.rmtree(baseFolderName)

    # Clean up base archive
    os.remove(baseArchiveName)

def prepareFiles(chapterName, dataFolderName):
    os.makedirs(f'temp/{dataFolderName}/StreamingAssets', exist_ok=True)
    os.makedirs(f'temp/{dataFolderName}/Managed', exist_ok=True)
    os.makedirs(f'temp/{dataFolderName}/Plugins', exist_ok=True)

    download(f'https://07th-mod.com/higurashi_dlls/{chapterName}/Assembly-CSharp.dll')
    print("Downloaded Unity dll")
    download('https://07th-mod.com/misc/AVProVideo.dll')
    print("Downloaded video plugin")


def buildPatch(chapterName, dataFolderName):
    # List of all folders used in releases. Dev and misc files are ignored
    folders = [
        "CG",
        "CGAlt",
        "SE",
        "voice",
        "spectrum",
        "BGM",
        "Update"
    ]

    # Iterates the list of folders above looking for valid folders in the master repo
    for folder in folders:
        try:
            shutil.move(f'{folder}', f'temp/{dataFolderName}/StreamingAssets')
        except:
            print(f'{folder} not found (this is ok)')

    try:
        shutil.move(f'tips.json', f'temp/{dataFolderName}')
    except:
        print(f'tips.json not found')
    shutil.move('Assembly-CSharp.dll', f'temp/{dataFolderName}/Managed')
    shutil.move('AVProVideo.dll', f'temp/{dataFolderName}/Plugins')


def makeArchive(chapterName, dataFolderName, gitTag):
    # Turns the first letter of the chapter name into uppercase for consistency when uploading a release
    upperChapter = chapterName.capitalize()
    os.makedirs(f'output', exist_ok=True)
    shutil.make_archive(base_name=f'output/{upperChapter}.Voice.and.Graphics.Patch.{gitTag}',
                        format='zip',
                        root_dir='temp',
                        base_dir=dataFolderName
                        )


def main():
    if sys.version_info < (3, 8):
        raise SystemExit(f"""ERROR: This script requires Python >= 3.8 to run (you have {sys.version_info.major}.{sys.version_info.minor})!

This script uses 3.8's 'dirs_exist_ok=True' argument for shutil.copy.""")

    argparser = argparse.ArgumentParser(usage='deploy_higurashi.py (onikakushi | watanagashi | tatarigoroshi | himatsubushi | meakashi | tsumihoroboshi | minagoroshi | matsuribayashi)',
                                        description='This script creates the "script" archive used in the Higurashi mod. It expects to be run from the root of one of the Higurashi mod repositories.')

    argparser.add_argument("chapter", help="The name of the chapter to be deployed.")
    argparser.add_argument(
        "--nocompile",
        dest="noCompile",
        action='store_true',
        help='Skips the script compilation step (archive will not have a CompiledUpdateScripts folder)',
    )

    args = argparser.parse_args()

    # Get Git Tag Environment Variables
    GIT_REF = os.environ.get("GITHUB_REF",  "unknown/unknown/X.Y.Z")    # Github Tag / Version info
    GIT_TAG = GIT_REF.split('/')[-1]
    print(f"--- Starting build for Git Ref: {GIT_REF} Git Tag: {GIT_TAG} ---")

    chapterList = [
        ChapterInfo("onikakushi",       1, "Onikakushi-UI_5.2.2f1_win.7z"),
        ChapterInfo("watanagashi",      2, "Watanagashi-UI_5.2.2f1_win.7z"),
        ChapterInfo("tatarigoroshi",    3, "Tatarigoroshi-UI_5.4.0f1_win.7z"),
        ChapterInfo("himatsubushi",     4, "Himatsubushi-UI_5.4.1f1_win.7z"),
        ChapterInfo("meakashi",         5, "Meakashi-UI_5.5.3p3_win.7z"),
        ChapterInfo("tsumihoroboshi",   6, "Tsumihoroboshi-UI_5.5.3p3_win.7z"),
        ChapterInfo("minagoroshi",      7, "Minagoroshi-UI_5.6.7f1_win.7z"),
        ChapterInfo("matsuribayashi",   8, "Matsuribayashi-UI_2017.2.5_win.7z")
    ]

    chapterDict = dict((chapter.name, chapter) for chapter in chapterList)

    chapter = chapterDict.get(args.chapter)

    if chapter is None:
        raise SystemExit(f"Error: Unknown Chapter '{args.chapter}' Selected\n\n{help}")

    # Compile every chapter's scripts before building archives
    if not args.noCompile:
        compileScripts(chapter)

    print(f">>> Creating folders and downloading necessary files")
    prepareFiles(chapter.name, chapter.dataFolderName)

    print(f">>> Building the patch")
    buildPatch(chapter.name, chapter.dataFolderName)

    print(f">>> Creating Archive")
    makeArchive(chapter.name, chapter.dataFolderName, GIT_TAG)

    print(f">>> Cleaning up the mess")
    shutil.rmtree('temp')

    # Set a Github Actions output "release_name" for use by the release step
    print(f'::set-output name=release_name::{chapter.name.capitalize()} Voice and Graphics Patch {GIT_TAG}')

if __name__ == "__main__":
    main()
