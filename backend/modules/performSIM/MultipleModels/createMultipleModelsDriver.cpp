#include <iostream>
#include <fstream>
#include <jansson.h> 
#include <string.h>
#include <string>
#include <sstream>
#include <list>
#include <vector>
#include <thread>
#include <filesystem>
#include <algorithm>

bool hasEnding (std::string const &fullString, std::string const &ending);

void eraseAllSubstring(std::string & mainStr, const std::string & toErase)
{
    size_t pos = std::string::npos;
    // Search for the substring in string in a loop untill nothing is found
    while ((pos  = mainStr.find(toErase) )!= std::string::npos)
    {
        // If found then erase it from string
        mainStr.erase(pos, toErase.length());
    }
}

int main(int argc, const char **argv) {
  std::string errMsg;
  std::ofstream theErrorFile; // Error log

  if (argc < 4) {
    std::cerr << "createOpenSeesDriver:: expecting 3 inputs\n";
    exit(-1);
  }

  std::string thisProgram(argv[0]);
  std::string inputFile(argv[1]);
  std::string runType(argv[2]);
  std::string osType(argv[3]);
  
  eraseAllSubstring(thisProgram,"\"");
  eraseAllSubstring(runType,"\"");
  eraseAllSubstring(osType,"\"");

  std::cerr << "runType: " << runType << '\n';
  std::cerr << "osType: " << osType << '\n';
  
  if (!std::filesystem::exists(inputFile)) {
    std::cerr << "createOpenSeesDriver:: input file: " << inputFile << " does not exist\n";
    exit(801);
  }



  
  //current_path(currentPath);
  auto path = std::filesystem::current_path(); //getting path


  //  std::string fileName = std::filesystem::path(inputFile).filename()
  std::filesystem::path fileNameP = std::filesystem::path(inputFile).filename();
  std::string fileName = fileNameP.generic_string(); 
  std::cerr << "fileName: " << fileName << '\n';  

  
  std::string fullPath = std::filesystem::path(inputFile).remove_filename().generic_string(); // templatedir
  std::string templateDir = std::filesystem::path(fullPath).parent_path().generic_string();


  std::filesystem::current_path(fullPath); //getting path
  path = std::filesystem::current_path(); //getting path
  std::cerr << "PATH: " << path << '\n';

  //
  // Creat dakota.err  at tmp.SimCenter
  //

  theErrorFile.open((std::filesystem::path(templateDir).parent_path().generic_string()+"/dakota.err").c_str(),std::ofstream::out );

  //
  // Get WorkflowApplication.json
  //


  std::string workflowAppsDir = std::filesystem::path(thisProgram).parent_path().parent_path().parent_path().generic_string() + "/WorkflowApplications.json";
  // IS THIS FINE?^
  json_error_t error;
  json_t *workflowApps = json_load_file(workflowAppsDir.c_str(), 0, &error);
  std::cerr << "PATH: " << workflowAppsDir << '\n';
  if (workflowApps == NULL) {
    std::stringstream errStream;
    errStream << "createMultipleModelsDriver:: workflowApplications file " << ((workflowAppsDir)) << " is not valid JSON";
    errMsg = errStream.str();
    std::cerr << errMsg << "\n";
    theErrorFile << errMsg << std::endl;
    theErrorFile.close();
    exit(801); 
  } 
  json_t *workflowFems = json_object_get(json_object_get(workflowApps,"femApplications"),"Applications");
  const int numWorkflowFems = json_array_size(workflowFems);
  std::cerr << "numWORKFLOWFEMS: " << numWorkflowFems << '\n';

  //
  // open input file to get RV's and EDP names
  //

  std::vector<std::string> rvList;  
  std::vector<std::string> edpList;
  
  json_t *rootInput = json_load_file(inputFile.c_str(), 0, &error);
  if (rootInput == NULL) {
    errMsg = "createMultipleModelsDriver:: input file " + inputFile + " is not valid JSON";
    std::cerr << errMsg << "\n";
    theErrorFile << errMsg << std::endl;
    theErrorFile.close();
    exit(801); 
  } 

  json_t *rootFEM =  json_object_get(rootInput, "fem");
  json_t *rootSubModels=  json_object_get(rootFEM, "submodels");

  const int numMod = json_integer_value(json_object_get(rootFEM,"numInputs"));
  std::cout <<"numModels:" + std::to_string(numMod) +"\n";

  for (int i =0; i<numMod ; i++) {

    int tag = i+1;

    // ====================================================================================
    // Copy templatedir
    // ====================================================================================
    
    std::string sub_template = templateDir + "." + std::to_string(tag);

    const auto copyOptions =
      std::filesystem::copy_options::update_existing
      | std::filesystem::copy_options::recursive;

    std::cerr << "PATH1: " << sub_template << '\n';
    std::cerr << "PATH2: " << fullPath << '\n';

    try
    {
      std::filesystem::copy(fullPath, sub_template, copyOptions);
    }

    catch (std::exception & e)
    {
      std::cout << e.what();
    }


    std::filesystem::current_path(sub_template); //getting path


    // ====================================================================================
    // Re-write FEM
    // ====================================================================================

    std::cout <<" model count:" + std::to_string(i) +"\n";


    json_t *copiedInput = json_deep_copy(rootInput);
    json_t *copiedSubModels=  json_object_get(json_object_get(copiedInput, "fem"), "submodels");

    bool tag_found = false;
    for (int j=0; j<numMod; j++) {

      json_t *model = json_array_get(copiedSubModels,j);
      const int tag_model = json_integer_value(json_object_get(model,"modelTag"));

      std::cout <<"tag_choosen:" << std::to_string(tag) <<std::endl;
      std::cout <<"tag_thismodel:" << tag_model <<std::endl;

      if (tag_model == tag) {
        std::cout <<"survived" <<std::endl;
        tag_found = true;
        json_object_set(copiedInput, "fem", model);
        break;
      } 
    }

    if (tag_found == false) {
      errMsg = "createMultipleModelsDriver:: modelTag " + std::to_string(tag) + " is not found";
      std::cerr << errMsg << "\n";
      theErrorFile << errMsg << std::endl;
      theErrorFile.close();
      exit(801); 
    }


    json_t *copiedRV=  json_object_get(copiedInput, "randomVariables");
  

    // ====================================================================================
    // Re-write RVs
    // ====================================================================================

    const int numRVs = json_array_size(copiedRV);
    std::cout <<"numRVs:" + std::to_string(numRVs) +"\n";

    for (int j=numRVs-1; j>-1; j--) { // for all RVs
      std::cout <<"  RVs count:" + std::to_string(j) +"\n";

      json_t *randomVariable = json_array_get(copiedRV,j);

      //const char *theRV = json_string_value(json_object_get(randomVariable,"value"));
      //std::string newRV(theRV);

      //std::string theRV(theRV_ch);
      std::string theRV = json_string_value(json_object_get(randomVariable,"name"));
      std::string theRVvalue = json_string_value(json_object_get(randomVariable,"value"));

      //std::string theRV("xx.2");
        //std::string tag_rv = std::string(1,'.') + std::to_string(k);
      //std::cout <<"  RVs count:" + std::to_string(j) +"\n";
      std::cout << "  RV Name: " << theRV <<"\n";    

      for (int k=0; k<numRVs; k++) { // inspect the tag
          //if (k+1 == tag) {
          //  continue;
          //}

          if (hasEnding(theRV,  "." + std::to_string(tag))) {
            std::string tag_string = "." + std::to_string(tag-1);
            json_object_set(randomVariable, "name", json_string(theRV.substr(0, theRV.size() - tag_string.size()).c_str())); // remove tag
            json_object_set(randomVariable, "value", json_string(theRVvalue.substr(0, theRVvalue.size() - tag_string.size()).c_str())); // remove tag
            std::cout <<"  saved " << theRVvalue << std::endl;

            continue;
          }

          if (hasEnding(theRV,  "." + std::to_string(k+1))) {
            //std::cout << json_string_value(json_object_get(randomVariable,"name")) << std::endl;
            json_array_remove(copiedRV, j);
            std::cout <<"  deleted " << std::endl;
            //break;
          }         
      }

      // const int numModelRVs = json_array_size(copiedRV);
      // for (int i=0; i<numModelRVs; i++) {
      //   if (hasEnding(theRV,  "." + std::to_string(tag))) {
      //     json_object_set(randomVariable, "name", json_string(theRV.substr(0, theRV.size() - 3).c_str())); // remove tag
      //   }
      // }

    }

    json_object_set(copiedInput, "randomVariables", copiedRV);


    std::string jsonFileName = "dakota."+ std::to_string(tag) +".json";
    //int rc = json_dump_file(copiedInput, fileName.c_str(), JSON_INDENT(1));
    int rc = json_dump_file(copiedInput, ("./" + jsonFileName).c_str(),  JSON_INDENT(1));
    if (rc) {
        fprintf(stderr, "cannot save json to file\n");
    }

   // ====================================================================================
   // create workflow driver
   // ====================================================================================


    const std::string programName = json_string_value(json_object_get(json_object_get(copiedInput, "fem"), "program"));
    std::string programExePath;
    std::cout << programName << programExePath <<"\n";    

    for (int j=0; j<numWorkflowFems; j++) {

      json_t *Fem = json_array_get(workflowFems,j);

      const std::string FemName = json_string_value(json_object_get(Fem,"Name"));
      std::cout << FemName << programExePath <<"\n";    

      if (FemName.compare(programName) == 0){
        std::cout << "caught" << programExePath <<"\n";    
          programExePath = json_string_value(json_object_get(Fem,"ExecutablePath"));
          break;
      }
    }
    std::cout << "  ================================================= " << programExePath <<"\n";    


    if (osType.compare("Windows") == 0) {
       programExePath = std::string("\"") + std::filesystem::path(workflowAppsDir).parent_path().parent_path().generic_string() +std::string("/")+  programExePath + std::string(".exe\"");
    } else {
       programExePath = std::string("\"") + std::filesystem::path(workflowAppsDir).parent_path().parent_path().generic_string()+std::string("/")+  programExePath;

    }
    std::cout << "  ================================================= " << programExePath <<"\n";    

    std::string commandWorkflowCreator  = programExePath + " " + sub_template +std::string("/")+ jsonFileName + " " +runType + " " + osType ;
    std::cout << "  ================================================= " << commandWorkflowCreator <<"\n";    
    system(commandWorkflowCreator.c_str());




    // std::string dpreproCommand;
    // std::string openSeesCommand;
    // std::string pythonCommand;
    // std::string feapCommand;
    // std::string moveCommand;

    // if (osType.compare("Windows") == 0) {
    //   dpreproCommand = std::string("../simCenterSub.exe\"");
    // } else {
    //   dpreproCommand = std::string("../simCenterSub\"");
    // }

    // if (programName.compare("OpenSees") == 0 {
    //     "../createOpenSeesDriver"

    // }





  }
  std::filesystem::current_path(fullPath); //getting path

}





//   json_t *rootRV =  json_object_get(rootInput, "randomVariables");
//   if (rootRV == NULL) {
//     std::cerr << "createOpenSeesDriver:: no randomVariables found\n";
//     return 0; // no random variables is allowed
//   }
  
//   json_t *rootEDP =  json_object_get(rootInput, "EDP");
//   if (rootEDP == NULL) {
//     std::cerr << "createOpenSeesDriver:: no EDP found\n";    
//     return 0; // no random variables is allowed
//   }

//   int numRV = getEDP(rootRV, rvList);  
//   int numEDP = getEDP(rootEDP, edpList);
  
//   //
//   // open workflow_driver 
//   //
  
//   std::string workflowDriver = "workflow_driver"; 
//   if ((osType.compare("Windows") == 0) && (runType.compare("runningLocal") == 0))
//     workflowDriver = "workflow_driver.bat";
  
//   std::ofstream workflowDriverFile(workflowDriver, std::ios::binary);
  
//   if (!workflowDriverFile.is_open()) {
//     std::cerr << "createOpenSeesDriver:: could not create workflow driver file: " << workflowDriver << "\n";
//     exit(802); // no random variables is allowed
//   }

//   std::string dpreproCommand;
//   std::string openSeesCommand;
//   std::string pythonCommand;
//   std::string feapCommand;
//   std::string moveCommand;

//   const char *localDir = json_string_value(json_object_get(rootInput,"localAppDir"));
//   const char *remoteDir = json_string_value(json_object_get(rootInput,"remoteAppDir"));

//   if (runType.compare("runningLocal") == 0) {

//     if (osType.compare("Windows") == 0) {
//       dpreproCommand = std::string("\"") + localDir + std::string("/applications/performUQ/templateSub/simCenterSub.exe\"");
//     } else {
//       dpreproCommand = std::string("\"") + localDir + std::string("/applications/performUQ/templateSub/simCenterSub\"");
//     }
    
//     openSeesCommand = std::string("OpenSees");
//     pythonCommand = std::string("\"") + json_string_value(json_object_get(rootInput,"python")) + std::string("\"");

//   } else {

//     dpreproCommand = remoteDir + std::string("/applications/performUQ/templateSub/simCenterSub");
//     openSeesCommand = std::string("/home1/00477/tg457427/bin/OpenSees");
//     pythonCommand = std::string("python");
//   }


//   json_t *fem =  json_object_get(rootInput, "fem");
//   if (fem == NULL) {
//     return 0; // no random variables is allowed
//   }
  
//   const char *mainInput =  json_string_value(json_object_get(fem, "mainInput"));
//   const char *postprocessScript =  json_string_value(json_object_get(fem, "mainPostprocessScript"));
    
//   int scriptType = 0;
//   if (strstr(postprocessScript,".py") != NULL) 
//     scriptType = 1;
//   else if (strstr(postprocessScript,".tcl") != NULL) 
//     scriptType = 2;
  
//   std::ofstream templateFile("SimCenterInput.RV");
//   for(std::vector<std::string>::iterator itRV = rvList.begin(); itRV != rvList.end(); ++itRV) {
//     templateFile << "pset " << *itRV << " \"RV." << *itRV << "\"\n";
//   }
  
//   templateFile << "\n set listQoI \"";
//   for(std::vector<std::string>::iterator itEDP = edpList.begin(); itEDP != edpList.end(); ++itEDP) {
//     templateFile << *itEDP << " ";
//   }
  
//   templateFile << "\"\n\n\n source " << mainInput << "\n";
  
//   workflowDriverFile << dpreproCommand << " params.in SimCenterInput.RV SimCenterInput.tcl\n";
//   workflowDriverFile << openSeesCommand << " SimCenterInput.tcl 1> ops.out 2>&1\n";


//   // depending on script type do something
//   if (scriptType == 1) { // python script
//     workflowDriverFile << "\n" << pythonCommand << " " << postprocessScript;
//     for(std::vector<std::string>::iterator itEDP = edpList.begin(); itEDP != edpList.end(); ++itEDP) {
//       workflowDriverFile << " " << *itEDP;
//     }
//   } 
//   else if (scriptType == 2) { // tcl script
//     templateFile << " source " << postprocessScript << "\n";      
//   }
  
//   templateFile.close();

//   workflowDriverFile.close();


//   try {
//     std::filesystem::permissions(workflowDriver,
// 				 std::filesystem::perms::owner_all |
// 				 std::filesystem::perms::group_all,
// 				 std::filesystem::perm_options::add);
//   }
//   catch (std::exception& e) {
//     std::cerr << "createOpenSeesDriver - failed in setting permissions\n";
//   }
    
//   //
//   // done
//   //

//   exit(0);
// }


bool hasEnding (std::string const &fullString, std::string const &ending) {
    if (fullString.length() >= ending.length()) {
        return (0 == fullString.compare (fullString.length() - ending.length(), ending.length(), ending));
    } else {
        return false;
    }
}
