#!/usr/bin/env python
############################################################################
# Created Time: 2021-12-13
# File Name: seGMM
# Last Change:.
# Description: a tool to infer gender from massively parallel sequencing data
############################################################################

import time, os, re, sys, argparse, traceback,subprocess
from functools import reduce
from pathlib import Path

def sec_to_str(t):
    '''Convert seconds to days:hours:minutes:seconds'''
    [d, h, m, s, n] = reduce(lambda ll, b : divmod(ll[0], b) + ll[1:], [(t, 1), 60, 60, 24])
    f = ''
    if d > 0:
        f += f'{d}d:'
    if h > 0:
        f += f'{h}h:'
    if m > 0:
        f += f'{m}m:'

    f += f'{s}s'
    return f

def runcmd(command):
    try:
        new_env = dict(os.environ)
        new_env['LC_ALL'] = 'C'
        return_info = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=new_env)
        error_code = bool(return_info.returncode)
        message = return_info.stdout.decode()
    except Exception as e:
        error_code = True
        message = e
    finally:
        if error_code:
            print(f"An error occured when running: '{command}'")
            print("Please check parameters!")
            print(message)
            sys.exit()

def collect_XH(input_vcf,outdir):
    print(">> Collected feature of X chromosome heterozygosity")
    cmd = "plink --vcf " + input_vcf + " --make-bed --out " + outdir+"/plink"
    runcmd(cmd)
    cmd = "plink --bfile " + outdir+"/plink"+ " --chr X --recode --out " + outdir+"/plink.X"
    runcmd(cmd)
    pedfile=outdir+"/plink.X.ped"
    outfile=outdir+"/XH.txt"
    if os.path.isfile(outfile):
        cmd="rm "+outfile
        runcmd(cmd)
    XH_list=[]
    with open(outfile,'a+')as xh:
        with open(pedfile) as f:
            line=f.readline()
            while line:
                lines=line.rstrip("\n").split(" ")
                het=0
                hom=0
                missing=0
                all_num=0
                for i in range(0,int((len(lines)-6)/2)):
                    if lines[i*2+4]!=lines[2*i+5]:
                        het+=1
                        all_num+=1
                    elif lines[i*2+4]==0:
                        missing+=1
                        all_num+=1
                    else:
                        hom+=1
                        all_num+=1
                if all_num!=missing:
                    xh.write(str(lines[0])+'\t'+str(het/(all_num-missing))+'\n')
                else:
                    xh.write(str(lines[0])+'\t'+float(0)+'\n')
                line=f.readline()
        f.close()
    xh.close()
    cmd="cat "+ outdir +"/XH.txt "+"| sort -n -k 1 >"+ outdir+"/XH.sorted.txt"
    runcmd(cmd)
    print(f'    Finish generate features of X chromosome heterozygosity at {time.ctime()} \n')

def collect_map(bamfile, fill_type, fasta, quality, num_threshold, outdir, regions=list()):
    if regions:
        basename = f"{regions[0]}map"
    else:
        basename = "total"

    print(f">> Collected feature of {basename} mapping rate")
    if not os.path.exists(outdir+"/"+"Read_stat"):
        os.makedirs(outdir+"/"+"Read_stat")

    option = ""
    if fill_type == "CRAM":
        if fasta == " ":
            sys.exit('Error, the fasta file for use with CRAM files is empty, please use --reference_fasta or -R!')
        elif not os.path.isfile(fasta):
            sys.exit('Error, the input reference fasta file is not exist, please check that you have provided the correct path!')
        option = f"-T {fasta}"
    
    cmd = f'''cat {bamfile} | awk '{{print $1"\\n"$2}}' | parallel -j {num_threshold} --max-args 2 samtools view -@ 10 -bh -q {quality} {option} {{2}} {" ".join(regions)} \\| samtools flagstat -@ 10 - \\>  {outdir}\\/Read_stat\\/{{1}}.{basename}.stat'''
    runcmd(cmd)
    cmd = f'''cat {bamfile} | awk '{{print $1}}' | while read id; do cat {outdir}/Read_stat/$id.{basename}.stat | awk 'BEGIN{{OFS="\\t"}}NR==9{{print "'$id'",$1}}' ;done | sort -n -k 1 > {outdir}/Read_stat/{basename}.txt'''
    runcmd(cmd)

    if basename != "total":
        cmd = f'''join {outdir}/Read_stat/{basename}.txt {outdir}/Read_stat/total.txt | awk 'BEGIN{{OFS="\\t"}}{{print $1,$2/$3}}' > {outdir}/{basename}.txt'''
        runcmd(cmd)

    print(f'    Finish generate features of {basename} mapping rate at {time.ctime()} \n')


def collect_SRY(bamfile,fill_type,fasta,quality,genome_version,outdir):
    print(">> Collected feature of mean depth of SRY gene")
    if not os.path.exists(outdir+"/"+"SRY"):
        os.makedirs(outdir+"/"+"SRY")
    if fill_type == "BAM": 
        cmd="cat " + bamfile + ''' | awk '{print $1,$2}' | while read id dir; do mosdepth -t 4 -Q ''' + quality + " -b " + str(Path(__file__).absolute().parent)+"/data/SRY_"+ genome_version + ".bed -n "+ outdir+"/"+"SRY/$id $dir; done"
        runcmd(cmd)
        cmd="cat "+bamfile+''' | awk '{print $1}' | while read id; do cat '''+outdir+"/SRY/$id.mosdepth.summary.txt | "+'''awk 'BEGIN{OFS="\\t"}NR==2{out1=$4}NR==3{out2=$4}END{if(out2!=0){print "'$id'",out2}else if(out1!=0){print "'$id'",out1}else{print "'$id'",0}}'; done | sort -n -k 1 >''' + outdir+"/SRY.txt"
        runcmd(cmd)
    elif fill_type == "CRAM":
        if fasta == " ":
            sys.exit('Error, the fasta file for use with CRAM files is empty, please use --reference_fasta or -R!')
        elif not os.path.isfile(fasta):
            sys.exit('Error, the input reference fasta file is not exist, please check that you have provided the correct path!')
        else:
            cmd="cat " + bamfile + ''' | awk '{print $1,$2}' | while read id dir; do mosdepth -t 4 -Q ''' + quality + " -f " + fasta + " -b " + str(Path(__file__).absolute().parent)+"/data/SRY_"+ genome_version + ".bed -n "+ outdir+"/"+"SRY/$id $dir; done"
            runcmd(cmd)
            cmd="cat "+bamfile+''' | awk '{print $1}' | while read id; do cat '''+outdir+"/SRY/$id.mosdepth.summary.txt | "+'''awk 'BEGIN{OFS="\\t"}NR==2{out1=$4}NR==3{out2=$4}END{if(out2!=0){print "'$id'",out2}else if(out1!=0){print "'$id'",out1}else{print "'$id'",0}}'; done | sort -n -k 1 >''' + outdir+"/SRY.txt"
            runcmd(cmd)
    print('    Finish generate features of mean depth of SRY gene at {T} \n'.format(T=time.ctime()))


def with_reference(feature, input_vcf,bamfile,fill_type,fasta,quality,num_threshold,genome_version,outdir):
    collect_map(bamfile,fill_type,fasta,quality,num_threshold,outdir)
    if feature == "XH":
        collect_XH(input_vcf,outdir)
    if feature == "Xmap":
        collect_map(bamfile,fill_type,fasta,quality,num_threshold,outdir,["X", "chrX"])
    if feature == "Ymap":
        collect_map(bamfile,fill_type,fasta,quality,num_threshold,outdir,["Y", "chrY"])
    if feature == "SRY":
        collect_SRY(bamfile,fill_type,fasta,quality,genome_version,outdir)
    if feature == "XYratio":
        Xmap = outdir+"/Xmap.txt"
        Ymap = outdir+"/Ymap.txt"
        if not os.path.isfile(Xmap):
            collect_map(bamfile,fill_type,fasta,quality,num_threshold,outdir,["X", "chrX"])
        if not os.path.isfile(Ymap):
            collect_map(bamfile,fill_type,fasta,quality,num_threshold,outdir,["Y", "chrY"])
        XYratio = outdir+"/XYratio.txt"
        cmd = "join "+Xmap+" " + Ymap + ''' | awk 'BEGIN{OFS="\\t"}{print $1,$2/$3}' >''' + XYratio
        runcmd(cmd)

def main():
    description = "seGMM is a tool for gender determination from massively parallel sequencing data based on Gaussian mixture model."
    __version__ = '1.3.0'
    header = "\n"
    header = "*********************************************************************\n"
    header += "* seGMM\n"
    header += f"* Version {__version__}\n"
    header += "* (C) 2021-2026 Sihan Liu\n"
    header += "* Research Institute of Rare disease / West china hospital\n"
    header += "* GNU General Public License v3\n"
    header += "*********************************************************************\n"

    end = "*********************************************************************\n"
    end += "* Thanks for using seGMM!\n"
    end += "* Report bugs to liusihan@wchscu.cn\n"
    end += "* seGMM homepage: https://github.com/liusihan/seGMM\n"
    end += "*********************************************************************"

#Usage
    parser = argparse.ArgumentParser(description = description)
    parser.add_argument("--vcf","-vcf",required = True,help = "Input VCF file (Either multi-sample or single-sample data. If the sample size is < 10, please combine with a reference data for prediction analysis).")
    parser.add_argument("--input","-i",required = True,help = "Input file contain sampleid and directory of bam/cram files (no header)")
    parser.add_argument("--alignment_format","-a",required = True,help = "Alignment format type for the input data",choices=["BAM","CRAM"])
    parser.add_argument("--reference_fasta","-R",required = False,help = "Reference genome for CRAM support (if CRAM is used). [default: '']")
    parser.add_argument("--chromosome","-c",required = False,help = "Sex chromosomes used to collect features. ",choices=["xy","x","y"])
    parser.add_argument("--type","-t",required = False,help = "Sequencing type. Note that if your don't provide an additional reference data, you must use --type. If the data type is WGS or WES, seGMM will automatic calculated all 5 features, otherwise if your data type is TGS you have to choice which sex chromosome you want to use and tell seGMM the SRY gene is included or not!",choices=["TGS","WES","WGS"])
    parser.add_argument("--output","-o",required = True,help = "Prefix of output directory.")
    parser.add_argument("--genome","-g",required = False,help = "Genome version. [default: hg19]. ",choices=["hg19","hg38"])
    parser.add_argument("--SRY","-s",required = False,help = "Extracting the average coverage of SRY gene.",choices=["True","False"])
    parser.add_argument("--reference_additional","-r",required = False,help = "Reference file which contain features.")
    parser.add_argument("--uncertain_threshold","-u",required = False,help = "The threshold for detecting outliers in GMM model. [default: 0.1]. The range of threshold is 0-1!",default=0.1)
    parser.add_argument("--num_threshold","-n",required = False,help = "Number of additional threads to use. [default: 1].")
    parser.add_argument("--quality","-q",required = False,help = "Mapping quality threshold of reads to count. [default: 30].")
    genome="hg19"
    uncertain_threshold="0.1"
    num_threshold="1"
    quality="30"
    fasta = " "
    args = parser.parse_args()
    print(header)
    try:
        if args.chromosome:
            chromosome=str(args.chromosome)
        if args.genome:
            genome=str(args.genome)
        if args.SRY:
            SRY=str(args.SRY)
        if args.uncertain_threshold:
            uncertain_threshold=str(args.uncertain_threshold)
        if args.num_threshold:
            num_threshold=str(args.num_threshold)
        if args.quality:
            quality=str(args.quality)
        if args.reference_fasta:
            fasta = str(os.path.realpath(args.reference_fasta))
        if (not os.path.isfile(fasta)) and fasta !=" ":
            sys.exit('Error, the reference genome file for CRAM support is not exist!')
        if args.alignment_format=="CRAM" and fasta==" ":
            sys.exit('Error, please provide reference genome file for CRAM support!')
        if not os.path.isfile(args.vcf):
            sys.exit('Error, the input vcf file is not exist, please check that you have provided the correct path!')
        if not os.path.isfile(args.input):
            sys.exit('Error, the input bam/cram file is not exist, please check that you have provided the correct path!')
        if not os.path.exists(args.output):
            os.makedirs(args.output)
            print(f"Warning, the output file is not exist, seGMM creates the output folder of {args.output} first!")
        if os.path.isfile(args.input) and os.path.isfile(args.vcf) and os.path.exists(args.output):
            if args.reference_additional is None:
                if args.type not in ["WES", "WGS", "TGS"]:
                    print("Please select the sequencing method for you data!")
                    sys.exit()
                if args.type == "TGS":
                    if args.chromosome not in ["x", "y", "xy"] or (args.chromosome=="x" and args.SRY=="True"):
                        print("Please note that you must choices the sex chromosome you want to use and tell seGMM the SRY gene is included in your reference data or not!")
                        sys.exit()
                    if (args.chromosome=="y" and args.SRY=="False"):
                        sys.exit('Error, at least 2 features are required by GMM model')
                
                print(f'Beginning to generate features at {time.ctime()}')
                start_time = time.time()
                join = []
                header, line, l = '"sampleid"', "$1", 1
                line = "$1"
                l = 1
                collect_map(args.input,args.alignment_format,fasta,quality,num_threshold,args.output)
                if args.type in ["WGS", "WES"] or (args.chromosome in ["x", "xy"]):
                    collect_XH(args.vcf,args.output)
                    collect_map(args.input,args.alignment_format,fasta,quality,num_threshold,args.output,["X", "chrX"])
                    join.append(f"{args.output}/XH.sorted.txt")
                    join.append(f"{args.output}/Xmap.txt")
                    header, line, l = f'{header},"XH","Xmap"', f'{line},${l+1},${l+2}', l+2
                if args.type in ["WGS", "WES"] or (args.chromosome in ["y", "xy"]):
                    collect_map(args.input,args.alignment_format,fasta,quality,num_threshold,args.output,["Y", "chrY"])
                    join.append(f"{args.output}/Ymap.txt")
                    header, line, l = f'{header},"Ymap"', f'{line},${l+1}', l+1
                if args.type in ["WGS", "WES"] or args.chromosome == "xy":
                    header, line = f'{header},"XYratio"', f'{line},${l-1}/${l}'
                if args.type in ["WGS", "WES"] or (args.SRY == "True"):
                    collect_SRY(args.input,args.alignment_format,fasta,quality,genome,args.output)
                    join.append(f"{args.output}/SRY.txt")
                    header, line, l = f'{header},"SRY"', f'{line},$NF', l+1
                cmd = 'join '
                for i, j in enumerate(join):
                    if i < 2:
                        cmd+=f"{j} "
                    else:
                        cmd += f"| join - {j} "
                cmd += f"""| awk 'BEGIN{{OFS="\\t";print {header}}}{{ print {line} }}' > {args.output}/feature.txt"""
                runcmd(cmd)
                print(">> Running sample classification based on GMM model")
                cmd=f"Rscript {str(Path(__file__).absolute().parent)}/script/seGMM.r {args.output}/feature.txt {str(uncertain_threshold)} {args.output}"
                runcmd(cmd)
            else:
                if not os.path.isfile(args.reference_additional):
                    print("The reference data is not exist!")
                    sys.exit()
                else:
                    ref = os.path.abspath(args.reference_additional)
                    if args.chromosome is None:
                        order = ["XH","Xmap","Ymap","XYratio","SRY"]
                        features = ["sampleid"]
                        with open(ref) as f:
                            line=f.readline()
                            header=line.rstrip("\n").split("\t")
                        f.close()
                        if header[0]!="sampleid":
                            sys.exit("Error, the first column for reference file must is sampleid!")
                        for i in range(1,len(header)):
                            if header[i] not in order:
                                sys.exit("Error. The header of reference data is wrong. "
                                    "Please make sure the header of reference data is: sampleid, XH, Xmap, Yamp, XYratio, SRY")
                            else:
                                features.append(header[i])
                        if len(features)<=1 :
                            sys.exit(
                                "Error. At least two of features required to be "
                                "included within reference file if runnning --refenrence.")
                        else:
                            print(f'Beginning generate features at {time.ctime()}')
                            start_time = time.time()
                            cmd = "cp " + ref + " " + args.output+"/feature.txt"
                            runcmd(cmd)
                            idx = 0
                            feature_combine = []
                            SRY = 0
                            XYratio = 0
                            for i in range(1,len(features)):
                                feature = args.output+"/"+features[i]+".txt"
                                if features[i] == "SRY":
                                    SRY = 1
                                    SRY_index = i
                                if features[i] == "XYratio":
                                    XYratio = 1
                                    XYratio_index = i
                                if not os.path.isfile(feature):
                                    with_reference(features[i], args.vcf,args.input,args.alignment_format,fasta,quality,num_threshold,genome,args.output)
                                if idx==0:
                                    with open(feature) as f:
                                        line=f.readline()
                                        while line:
                                            lines=line.rstrip("\n").split("\t")
                                            feature_combine.append(lines)
                                            line = f.readline()
                                    f.close()
                                    idx=1
                                else:
                                    line_num=0
                                    with open(feature) as f:
                                        line=f.readline()
                                        while line:
                                            lines=line.rstrip("\n").split("\t")
                                            feature_combine[line_num].append(lines[1])
                                            line_num += 1
                                            line=f.readline()
                                    f.close()
                            feature_file = args.output+"/feature.txt"
                            with open(feature_file,'a+')as xh:
                                for i in range(0,len(feature_combine)):
                                    if XYratio == 1 and SRY == 1:
                                        feature_combine[i][SRY_index] = str(float(feature_combine[i][SRY_index])/float(feature_combine[i][XYratio_index]))
                                    xh.write('\t'.join(feature_combine[i])+'\n')
                            xh.close()
                        print(">> Running sample classfication based on GMM model")
                        cmd="Rscript "+ str(Path(__file__).absolute().parent)+"/script/seGMM.r " +args.output+"/feature.txt "+str(uncertain_threshold)+" "+args.output
                        runcmd(cmd)
                    else:
                        print("Error, the --chromosome paremeter is not useful with an additional file!")
                        sys.exit()
        print(f'\nAnalysis complete for seGMM at {time.ctime()}')
        time_elapsed = round(time.time()-start_time,2)
        print(f'Total time elapsed: {sec_to_str(time_elapsed)} \n')
        print(end)
    except Exception:
        print("Error, please read the protocol of seGMM")
        raise

if __name__ == '__main__':
    main()
