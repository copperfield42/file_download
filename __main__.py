from file_download import download
import sys 

if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv:
        if "-h" in argv:
            print("file_download url nombre [path]")
        else:
            #u,n,p,*e = [*argv,os.getcwd()]
            print("resultado en: "+download(*argv))