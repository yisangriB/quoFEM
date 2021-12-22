#include <iostream>
#include <fstream>
#include <jansson.h>
#include <string.h>
#include <string>
#include <sstream>
#include <list>
#include <vector>

struct normalRV {
  std::string name;
  double mean;
  double stdDev;
};

struct lognormalRV {
  std::string name;
  double mean;
  double stdDev;
};

struct constantRV {
  std::string name;
  double value;
};

struct uniformRV {
  std::string name;
  double lowerBound;
  double upperBound;
};

struct continuousDesignRV {
  std::string name;
  double lowerBound;
  double upperBound;
  double initialPoint;
};

struct weibullRV {
  std::string name;
  double scaleParam;
  double shapeParam;
};

struct gammaRV {
  std::string name;
  double alphas;
  double betas;
};

struct gumbellRV {
  std::string name;
  double alphas;
  double betas;
};

struct betaRV {
  std::string name;
  double alphas;
  double betas;
  double lowerBound;
  double upperBound;
};

struct discreteDesignSetRV {
  std::string name;
  std::list<std::string> elements;
};

struct randomVariables {
  int numRandomVariables;
  std::list<struct normalRV> normalRVs;
  std::list<struct lognormalRV> lognormalRVs;
  std::list<struct constantRV> constantRVs;
  std::list<struct uniformRV> uniformRVs;
  std::list<struct continuousDesignRV> continuousDesignRVs;
  std::list<struct weibullRV> weibullRVs;
  std::list<struct gammaRV> gammaRVs;
  std::list<struct gumbellRV> gumbellRVs;
  std::list<struct betaRV> betaRVs;
  std::list<struct discreteDesignSetRV> discreteDesignSetRVs;
  std::vector<int> ordering;
  std::vector<double> corrMat;
  //std::vector<double> corrMat;
  //json_t* corrMat;
};


// parses JSON for random variables & returns number found

int
parseForRV(json_t *root, struct randomVariables &theRandomVariables){
  int numberRVs = 0;

  json_t *fileRandomVariables =  json_object_get(root, "randomVariables");
  if (fileRandomVariables == NULL) {
    return 0; // no random variables is allowed
  }

  int numRVs = json_array_size(fileRandomVariables);
  for (int i=0; i<numRVs; i++) {
    json_t *fileRandomVariable = json_array_get(fileRandomVariables,i);
    const char *variableType = json_string_value(json_object_get(fileRandomVariable,"distribution"));

    if ((strcmp(variableType, "Normal") == 0) || (strcmp(variableType, "normal")==0)) {

      struct normalRV theRV;

      theRV.name = json_string_value(json_object_get(fileRandomVariable,"name"));
      theRV.mean = json_number_value(json_object_get(fileRandomVariable,"mean"));
      theRV.stdDev = json_number_value(json_object_get(fileRandomVariable,"stdDev"));

      theRandomVariables.normalRVs.push_back(theRV);
      theRandomVariables.numRandomVariables += 1;
      theRandomVariables.ordering.push_back(1);
      numberRVs++;

    }

    else if ((strcmp(variableType, "Lognormal") == 0) || (strcmp(variableType, "lognormal") == 0)) {

      struct lognormalRV theRV;

      theRV.name = json_string_value(json_object_get(fileRandomVariable,"name"));
      theRV.mean = json_number_value(json_object_get(fileRandomVariable,"mean"));
      theRV.stdDev = json_number_value(json_object_get(fileRandomVariable,"stdDev"));

      theRandomVariables.lognormalRVs.push_back(theRV);
      theRandomVariables.numRandomVariables += 1;
      theRandomVariables.ordering.push_back(2);
      numberRVs++;

    }


    else if (strcmp(variableType, "Uniform") == 0) {

      struct uniformRV theRV;

      theRV.name = json_string_value(json_object_get(fileRandomVariable,"name"));
      theRV.lowerBound = json_number_value(json_object_get(fileRandomVariable,"lowerbound"));
      theRV.upperBound = json_number_value(json_object_get(fileRandomVariable,"upperbound"));

      theRandomVariables.uniformRVs.push_back(theRV);
      theRandomVariables.numRandomVariables += 1;
      theRandomVariables.ordering.push_back(3);
      numberRVs++;

    }


    else if (strcmp(variableType, "Constant") == 0) {

      struct constantRV theRV;
      theRV.name = json_string_value(json_object_get(fileRandomVariable,"name"));
      theRV.value = json_number_value(json_object_get(fileRandomVariable,"value"));

      theRandomVariables.constantRVs.push_back(theRV);
      theRandomVariables.numRandomVariables += 1;
      numberRVs++;

    }



    else if (strcmp(variableType, "ContinuousDesign") == 0) {
      struct continuousDesignRV theRV;

      theRV.name = json_string_value(json_object_get(fileRandomVariable,"name"));
      theRV.lowerBound = json_number_value(json_object_get(fileRandomVariable,"lowerbound"));
      theRV.upperBound = json_number_value(json_object_get(fileRandomVariable,"upperbound"));
      theRV.initialPoint = json_number_value(json_object_get(fileRandomVariable,"initialpoint"));

      theRandomVariables.continuousDesignRVs.push_back(theRV);
      theRandomVariables.numRandomVariables += 1;
      numberRVs++;
    }

    else if (strcmp(variableType, "Weibull") == 0) {

      struct weibullRV theRV;

      theRV.name = json_string_value(json_object_get(fileRandomVariable,"name"));
      theRV.shapeParam = json_number_value(json_object_get(fileRandomVariable,"shapeparam"));
      theRV.scaleParam = json_number_value(json_object_get(fileRandomVariable,"scaleparam"));

      theRandomVariables.weibullRVs.push_back(theRV);
      theRandomVariables.numRandomVariables += 1;
      theRandomVariables.ordering.push_back(11);
      numberRVs++;
    }

    else if (strcmp(variableType, "Gamma") == 0) {

      struct gammaRV theRV;

      theRV.name = json_string_value(json_object_get(fileRandomVariable,"name"));
      theRV.alphas = json_number_value(json_object_get(fileRandomVariable,"alphas"));
      theRV.betas = json_number_value(json_object_get(fileRandomVariable,"betas"));

      theRandomVariables.gammaRVs.push_back(theRV);
      theRandomVariables.numRandomVariables += 1;
      theRandomVariables.ordering.push_back(8);
      numberRVs++;
    }

    else if (strcmp(variableType, "Gumbel") == 0) {

      struct gumbellRV theRV;

      theRV.name = json_string_value(json_object_get(fileRandomVariable,"name"));
      theRV.alphas = json_number_value(json_object_get(fileRandomVariable,"alphaparam"));
      theRV.betas = json_number_value(json_object_get(fileRandomVariable,"betaparam"));

      theRandomVariables.gumbellRVs.push_back(theRV);
      theRandomVariables.numRandomVariables += 1;
      theRandomVariables.ordering.push_back(9);
      numberRVs++;
    }


    else if (strcmp(variableType, "Beta") == 0) {

      struct betaRV theRV;

      theRV.name = json_string_value(json_object_get(fileRandomVariable,"name"));
      theRV.alphas = json_number_value(json_object_get(fileRandomVariable,"alphas"));
      theRV.betas = json_number_value(json_object_get(fileRandomVariable,"betas"));
      theRV.lowerBound = json_number_value(json_object_get(fileRandomVariable,"lowerbound"));
      theRV.upperBound = json_number_value(json_object_get(fileRandomVariable,"upperbound"));
      std::cerr << theRV.name << " " << theRV.upperBound << " " << theRV.lowerBound << " " << theRV.alphas << " " << theRV.betas;
      theRandomVariables.betaRVs.push_back(theRV);
      theRandomVariables.numRandomVariables += 1;
      theRandomVariables.ordering.push_back(7);
      numberRVs++;
    }

    else if (strcmp(variableType, "discrete_design_set_string") == 0) {

      struct discreteDesignSetRV theRV;

      theRV.name = json_string_value(json_object_get(fileRandomVariable,"name"));
      std::list<std::string> theValues;
      json_t *elementsSet =  json_object_get(fileRandomVariable, "elements");
      if (elementsSet != NULL) {

    	int numValues = json_array_size(elementsSet);
    	for (int j=0; j<numValues; j++) {
    	  json_t *element = json_array_get(elementsSet,j);
    	  std::string value = json_string_value(element);
    	    theValues.push_back(value);
    	}

    	theRV.elements = theValues;

    	theRandomVariables.discreteDesignSetRVs.push_back(theRV);
    	theRandomVariables.numRandomVariables += 1;
    	numberRVs++;
      }
    }

    json_t* corrMatJson =  json_object_get(root,"correlationMatrix");
    if (corrMatJson != NULL) {
      int numCorrs = json_array_size(corrMatJson);
      for (int i=0; i<numCorrs; i++) {
        const double corrVal = json_number_value(json_array_get(corrMatJson,i));
        theRandomVariables.corrMat.push_back(corrVal);
      }
    } else {
      theRandomVariables.corrMat.push_back(0.0);
    }


  } // end loop over random variables

  return numRVs;
}


int
writeRV(std::ostream &dakotaFile, struct randomVariables &theRandomVariables, std::string idVariables, std::vector<std::string> &rvList, bool includeActiveText = true){


    int numContinuousDesign = theRandomVariables.continuousDesignRVs.size();

    if (numContinuousDesign != 0) {

      if (idVariables.empty())
	dakotaFile << "variables \n ";
      else
	dakotaFile << "variables \n id_variables =  '" << idVariables << "'\n";

      if (numContinuousDesign > 0) {
	dakotaFile << "  continuous_design = " << numContinuousDesign << "\n    initial_point = ";
	// std::list<struct continuousDesignRV>::iterator it;
	for (auto it = theRandomVariables.continuousDesignRVs.begin(); it != theRandomVariables.continuousDesignRVs.end(); it++)
	  dakotaFile << it->initialPoint << " ";
	dakotaFile << "\n    lower_bounds = ";
	for (auto it = theRandomVariables.continuousDesignRVs.begin(); it != theRandomVariables.continuousDesignRVs.end(); it++)
	  dakotaFile << it->lowerBound << " ";
	dakotaFile << "\n    upper_bounds = ";
	for (auto it = theRandomVariables.continuousDesignRVs.begin(); it != theRandomVariables.continuousDesignRVs.end(); it++)
	  dakotaFile << it->upperBound << " ";
	dakotaFile << "\n    descriptors = ";
	for (auto it = theRandomVariables.continuousDesignRVs.begin(); it != theRandomVariables.continuousDesignRVs.end(); it++) {
	  dakotaFile << "\'" << it->name << "\' ";
	  rvList.push_back(it->name);
	}
	dakotaFile << "\n\n";
      }
      return 0;
    }

    if (includeActiveText == true) {
      if (idVariables.empty())
	dakotaFile << "variables \n active uncertain \n";
      else
	dakotaFile << "variables \n id_variables =  '" << idVariables << "'\n active uncertain \n";
    } else {
	dakotaFile << "variables \n";
    }

      int numNormalUncertain = theRandomVariables.normalRVs.size();

    int numNormal = theRandomVariables.normalRVs.size();
    if (theRandomVariables.normalRVs.size() > 0) {
      dakotaFile << "  normal_uncertain = " << numNormal << "\n    means = ";
      // std::list<struct normalRV>::iterator it;
      for (auto it = theRandomVariables.normalRVs.begin(); it != theRandomVariables.normalRVs.end(); it++)
	dakotaFile << it->mean << " ";
      dakotaFile << "\n    std_deviations = ";
      for (auto it = theRandomVariables.normalRVs.begin(); it != theRandomVariables.normalRVs.end(); it++)
	dakotaFile << it->stdDev << " ";
      dakotaFile << "\n    descriptors = ";
      for (auto it = theRandomVariables.normalRVs.begin(); it != theRandomVariables.normalRVs.end(); it++) {
	dakotaFile << "\'" << it->name << "\' ";
	rvList.push_back(it->name);
      }

      dakotaFile << "\n";
    }

    int numLognormal = theRandomVariables.lognormalRVs.size();
    if (numLognormal > 0) {
      dakotaFile << "  lognormal_uncertain = " << numLognormal << "\n    means = ";
      //      std::list<struct lognormalRV>::iterator it;
      for (auto it = theRandomVariables.lognormalRVs.begin(); it != theRandomVariables.lognormalRVs.end(); it++)
	dakotaFile << it->mean << " ";
      dakotaFile << "\n    std_deviations = ";
      for (auto it = theRandomVariables.lognormalRVs.begin(); it != theRandomVariables.lognormalRVs.end(); it++)
	dakotaFile << it->stdDev << " ";
      dakotaFile << "\n    descriptors = ";
      for (auto it = theRandomVariables.lognormalRVs.begin(); it != theRandomVariables.lognormalRVs.end(); it++) {
	dakotaFile << "\'" << it->name << "\' ";
	rvList.push_back(it->name);
      }
      dakotaFile << "\n";
    }

    int numUniform = theRandomVariables.uniformRVs.size();
    if (numUniform > 0) {
      dakotaFile << "  uniform_uncertain = " << numUniform << "\n    lower_bounds = ";
      // std::list<struct uniformRV>::iterator it;
      for (auto it = theRandomVariables.uniformRVs.begin(); it != theRandomVariables.uniformRVs.end(); it++)
	dakotaFile << it->lowerBound << " ";
      dakotaFile << "\n    upper_bound = ";
      for (auto it = theRandomVariables.uniformRVs.begin(); it != theRandomVariables.uniformRVs.end(); it++)
	dakotaFile << it->upperBound << " ";
      dakotaFile << "\n    descriptors = ";
      for (auto it = theRandomVariables.uniformRVs.begin(); it != theRandomVariables.uniformRVs.end(); it++) {
	dakotaFile << "\'" << it->name << "\' ";
	rvList.push_back(it->name);
      }
      dakotaFile << "\n";
    }


    int numWeibull = theRandomVariables.weibullRVs.size();
    if (numWeibull > 0) {
      dakotaFile << "  weibull_uncertain = " << numWeibull << "\n    alphas = ";
      // std::list<struct weibullRV>::iterator it;
      for (auto it = theRandomVariables.weibullRVs.begin(); it != theRandomVariables.weibullRVs.end(); it++)
	dakotaFile << it->shapeParam << " ";
      dakotaFile << "\n    betas = ";
      for (auto it = theRandomVariables.weibullRVs.begin(); it != theRandomVariables.weibullRVs.end(); it++)
	dakotaFile << it->scaleParam << " ";
      dakotaFile << "\n    descriptors = ";
      for (auto it = theRandomVariables.weibullRVs.begin(); it != theRandomVariables.weibullRVs.end(); it++) {
	dakotaFile << "\'" << it->name << "\' ";
	rvList.push_back(it->name);
      }
      dakotaFile << "\n";
    }

    int numGumbell = theRandomVariables.gumbellRVs.size();
    if (numGumbell > 0) {
      dakotaFile << "  gumbel_uncertain = " << numGumbell << "\n    alphas = ";
      // std::list<struct gumbellRV>::iterator it;
      for (auto it = theRandomVariables.gumbellRVs.begin(); it != theRandomVariables.gumbellRVs.end(); it++)
	dakotaFile << it->alphas << " ";
      dakotaFile << "\n    betas = ";
      for (auto it = theRandomVariables.gumbellRVs.begin(); it != theRandomVariables.gumbellRVs.end(); it++)
	dakotaFile << it->betas << " ";
      dakotaFile << "\n    descriptors = ";
      for (auto it = theRandomVariables.gumbellRVs.begin(); it != theRandomVariables.gumbellRVs.end(); it++) {
	dakotaFile << "\'" << it->name << "\' ";
	rvList.push_back(it->name);
      }
      dakotaFile << "\n";
    }


    int numGamma = theRandomVariables.gammaRVs.size();
    if (numGamma > 0) {
      dakotaFile << "  gamma_uncertain = " << numGamma << "\n    alphas = ";
      std::list<struct gammaRV>::iterator it;
      for (auto it = theRandomVariables.gammaRVs.begin(); it != theRandomVariables.gammaRVs.end(); it++)
	dakotaFile << it->alphas << " ";
      dakotaFile << "\n    betas = ";
      for (auto it = theRandomVariables.gammaRVs.begin(); it != theRandomVariables.gammaRVs.end(); it++)
	dakotaFile << it->betas << " ";
      dakotaFile << "\n    descriptors = ";
      for (auto it = theRandomVariables.gammaRVs.begin(); it != theRandomVariables.gammaRVs.end(); it++) {
	dakotaFile << "\'" << it->name << "\' ";
	rvList.push_back(it->name);
      }
      dakotaFile << "\n";
    }

    int numBeta = theRandomVariables.betaRVs.size();
    if (numBeta > 0) {
      dakotaFile << "  beta_uncertain = " << numBeta << "\n    alphas = ";
      //std::list<struct betaRV>::iterator it;
      for (auto it = theRandomVariables.betaRVs.begin(); it != theRandomVariables.betaRVs.end(); it++)
	dakotaFile << it->alphas << " ";
      dakotaFile << "\n    betas = ";
      for (auto it = theRandomVariables.betaRVs.begin(); it != theRandomVariables.betaRVs.end(); it++)
	dakotaFile << it->betas << " ";
      dakotaFile << "\n    lower_bounds = ";
      for (auto it = theRandomVariables.betaRVs.begin(); it != theRandomVariables.betaRVs.end(); it++)
	dakotaFile << it->lowerBound << " ";
      dakotaFile << "\n    upper_bounds = ";
      for (auto it = theRandomVariables.betaRVs.begin(); it != theRandomVariables.betaRVs.end(); it++)
	dakotaFile << it->upperBound << " ";
      dakotaFile << "\n    descriptors = ";
      for (auto it = theRandomVariables.betaRVs.begin(); it != theRandomVariables.betaRVs.end(); it++) {
	dakotaFile << "\'" << it->name << "\' ";
	rvList.push_back(it->name);
      }
      dakotaFile << "\n";
    }

    int numConstant = theRandomVariables.constantRVs.size();
    if (numConstant > 0) {
      dakotaFile << "  discrete_state_set  \n    real = " << numConstant;
      dakotaFile << "\n    elements_per_variable = ";
      for (auto it = theRandomVariables.constantRVs.begin(); it != theRandomVariables.constantRVs.end(); it++)
        dakotaFile << "1 ";     //std::list<struct betaRV>::iterator it;
      dakotaFile << "\n    elements = ";
      for (auto it = theRandomVariables.constantRVs.begin(); it != theRandomVariables.constantRVs.end(); it++)
        dakotaFile << it->value << " ";
      dakotaFile << "\n    descriptors = ";
      for (auto it = theRandomVariables.constantRVs.begin(); it != theRandomVariables.constantRVs.end(); it++) {
        dakotaFile << "\'" << it->name << "\' ";
        rvList.push_back(it->name);
      }
      dakotaFile << "\n";
    }

    //nt numConstant = theRandomVariables.constantRVs.size();
    //#if (numConstant > 0) {
    //  for (auto it = theRandomVariables.constantRVs.begin(); it != theRandomVariables.constantRVs.end(); it++) {
    //    rvList.push_back(it->name);
    //  }
    //}    

    int numDiscreteDesignSet = theRandomVariables.discreteDesignSetRVs.size();
    if (numDiscreteDesignSet > 0) {
      dakotaFile << "    discrete_uncertain_set\n    string " << numDiscreteDesignSet << "\n    num_set_values = ";
      std::list<struct discreteDesignSetRV>::iterator it;
      for (it = theRandomVariables.discreteDesignSetRVs.begin(); it != theRandomVariables.discreteDesignSetRVs.end(); it++)
	dakotaFile << it->elements.size() << " ";
      dakotaFile << "\n    set_values ";
      for (it = theRandomVariables.discreteDesignSetRVs.begin(); it != theRandomVariables.discreteDesignSetRVs.end(); it++) {
	it->elements.sort(); // sort the elements NEEDED THOUGH NOT IN DAKOTA DOC!
	std::list<std::string>::iterator element;
	for (element = it->elements.begin(); element != it->elements.end(); element++)
	  dakotaFile << " \'" << *element << "\'";
      }
      dakotaFile << "\n    descriptors = ";
      for (auto it = theRandomVariables.discreteDesignSetRVs.begin(); it != theRandomVariables.discreteDesignSetRVs.end(); it++) {
	dakotaFile << "\'" << it->name << "\' ";
	rvList.push_back(it->name);
      }
      dakotaFile << "\n";
    }

    // if no random variables .. create 1 call & call it dummy!
    int numRV = theRandomVariables.numRandomVariables;
    if (numRV == 0) {
      dakotaFile << "   discrete_uncertain_set\n    string 1 \n    num_set_values = 2";
      dakotaFile << "\n    set_values  '1' '2'";
      dakotaFile << "\n    descriptors = dummy\n";
      rvList.push_back(std::string("dummy"));
    }
    dakotaFile << "\n";

    // if correlations, (sy)
     //if (theRandomVariables.corrMat[0] != 0) {

    if (!theRandomVariables.corrMat.empty()) {
      
      if (theRandomVariables.corrMat[0]!=0) {

        std::vector<int> newOrder;
        for (int i=0; i<18; i++) {
           for (int j=0; j<theRandomVariables.ordering.size(); j++) {
             if (i==theRandomVariables.ordering[j]) {
                newOrder.push_back(j);
             }
          }         
        }


        dakotaFile<<"uncertain_correlation_matrix\n";
        for (int i : newOrder) {
          dakotaFile << "    ";
          for (int j : newOrder) {
            double corrval = theRandomVariables.corrMat[i*theRandomVariables.numRandomVariables+j];
            dakotaFile << corrval << " ";
          }
          dakotaFile << "\n";
        }
      }
    }
    dakotaFile << "\n\n";

    return 0;
}

int
writeInterface(std::ostream &dakotaFile, json_t *uqData, std::string &workflowDriver, std::string idInterface, int evalConcurrency) {

  dakotaFile << "interface \n";
  if (!idInterface.empty())
    dakotaFile << "  id_interface = '" << idInterface << "'\n";

  dakotaFile << "  analysis_driver = '" << workflowDriver << "'\n";
  dakotaFile << "  file_save\n";
  dakotaFile << "  fork\n";

  dakotaFile << "   parameters_file = 'paramsDakota.in'\n";
  dakotaFile << "   results_file = 'results.out' \n";
  dakotaFile << "   aprepro \n";
  dakotaFile << "   work_directory\n";
  dakotaFile << "     named \'workdir\' \n";
  dakotaFile << "     directory_tag\n";
  dakotaFile << "     directory_save\n";

  /*
    if uqData['keepSamples']:
        dakota_input += ('        directory_save\n')
  */

  dakotaFile << "     copy_files = 'templatedir/*' \n";
  if (evalConcurrency > 0)
    dakotaFile << "  asynchronous evaluation_concurrency = " << evalConcurrency << "\n\n";
  else
    dakotaFile << "  asynchronous \n\n";

  /*
  if (runType == "local") {
    uqData['concurrency'] = uqData.get('concurrency', 4)
  }
  if uqData['concurrency'] == None:
     dakota_input += "  asynchronous\n"
  elif uqData['concurrency'] > 1:
     dakota_input += "  asynchronous evaluation_concurrency = {}\n".format(uqData['concurrency'])
  }
  */

  return 0;
}


int processDataFiles(const char *calFileName,
                     std::vector<std::string> &edpList,
                     std::vector<int> &lengthList,
                     int numResponses, int numFieldResponses,
                     std::vector<std::string> &errFileList,
                     std::stringstream &errType, std::string idResponse,
                     std::vector<double> &scaleFactors) {

    std::ifstream calDataFile;
    calDataFile.open(calFileName, std::ios_base::in);

    // Compute the expected length of each line and cumulative length corresponding to the responses
    // within each line
    int lineLength = 0;
    std::vector<int> cumLenList(numResponses, 0);
    for (int i = 0; i < numResponses; i++) {
        lineLength += lengthList[i];
        cumLenList[i] += lineLength;
    }

    // Create an fstream to write the calibration data after removing all commas
    std::fstream spacedDataFile;
    std::string spacedFileName = "quoFEMTempCalibrationDataFile.cal";
    spacedDataFile.open(spacedFileName.c_str(), std::fstream::out);
    // Check if open succeeded
    if (!spacedDataFile) {
        std::cerr << "ERROR: unable to open file: " << spacedFileName << std::endl;
        return EXIT_FAILURE;
    }

    // Count the number of experiments, check the length of each line, remove commas and write data to a temp file
    int numExperiments = 0;
    std::string line;
    int lineNum = 0;
    // For each line in the calibration data file
    while (getline(calDataFile, line)) {
        // Get a string stream for each line
        std::stringstream lineStream(line);
        if (!line.empty()) {
            ++lineNum;
            int wordCount = 0;
            // Check length of each line
            char *word;
            word = strtok(const_cast<char *>(line.c_str()), " \t,");
            while (word != nullptr) { // while end of cstring is not reached
                ++wordCount;
                spacedDataFile << word << " ";
                word = strtok(nullptr, " \t,");
            }
            if (wordCount != lineLength) {
                std::cout << std::endl << "ERROR: The number of calibration terms expected in each line is "
                          << lineLength
                          << ", but the length of line " << lineNum << " is " << wordCount << ". Aborting."
                          << std::endl;
                spacedDataFile.close();
                return EXIT_FAILURE;
            }

            spacedDataFile << std::endl;
        }
    }
    numExperiments = lineNum;
    spacedDataFile.close();
    calDataFile.clear();
    calDataFile.close();

    std::string filename = calFileName;
    std::string calDirectory;
    const size_t last_slash_idx = filename.rfind('\\/');
    if (std::string::npos != last_slash_idx)
    {
        calDirectory = filename.substr(0, last_slash_idx);
    }
    for (int expNum = 1; expNum <= numExperiments; expNum++) {
        for (int responseNum = 0; responseNum < numResponses; responseNum++) {
            std::stringstream errFileName;
            errFileName << edpList[responseNum] << "." << expNum << ".sigma";
            std::ifstream checkFile(errFileName.str());
            if (checkFile.good()) {
                errFileList.push_back(errFileName.str());
            }
        }
    }

    // Check if there are any files describing the error covariance structure in errFileList
    bool readErrorFile = false;
    if (!errFileList.empty()) {
        readErrorFile = true;
    }

    // Start making a list of all the calibration data files to be moved to the upper directory
    std::string trackerFileName = "calibrationDataFilesToMove.cal";
    std::ofstream calFilesTracker;
    calFilesTracker.open(trackerFileName.c_str(), std::ofstream::out);

    // =============================================
    // When there are any non-scalar response terms
    // =============================================
    if (numFieldResponses > 0) {
        std::string calDataLine;
        calDataFile.open(spacedFileName.c_str());

        // For each line in the calibration data file
        while (getline(calDataFile, calDataLine)) {
            if (!calDataLine.empty()) {
                std::stringstream lineStream(calDataLine);
                int wordCount = 0;

                // For each response quantity, create a data file and write the corresponding data to it
                for (int responseNum = 0; responseNum < numResponses; responseNum++) {

                    // =============================================
                    // Create a file for each response variable data
                    std::stringstream fName;
                    fName << edpList[responseNum] << "." << lineNum << ".dat";
                    std::ofstream outfile;
                    outfile.open(fName.str().c_str());
                    // Get the calibration terms corresponding to length of each response quantity
                    while (wordCount < cumLenList[responseNum]) {
                        std::string word;
                        lineStream >> word;
                        outfile << word << std::endl;
                        wordCount++;
                    }
                    // Close the file
                    outfile.close();
                    // Add this filename to the file containing the list of files to move to upper directory
                    calFilesTracker << fName.str() << std::endl;
                    // =============================================

                    // Only for Bayesian calibration - create error covariance files per response per experiment
                    if (idResponse.compare("BayesCalibration") == 0) {
                        // =============================================
                        // Create filename for error variance
                        std::stringstream errFileName;
                        errFileName << edpList[responseNum] << "." << lineNum << ".sigma";
                        std::ofstream errFile;

                        // Check if an error variance file with the created name is in the list of error files
                        bool createErrFile = true;
                        std::string errFileToProcess;
                        if (readErrorFile) {
                            for (const auto &path : errFileList) {
                                std::string base_filename = path.substr(path.find_last_of("/\\") + 1);
                                if (base_filename == errFileName.str()) {
                                    createErrFile = false;
                                    errFileToProcess = path;
                                    break;
                                }
                            }
                        }
                        // If there is no user-supplied error covariance file with the created name, create error file
                        if (createErrFile) {
                            errFile.open(errFileName.str().c_str());
                            // Write the default error covariance - scalar with variance 1
                            errFile << "1" << std::endl;
                            errType << "'scalar' ";
                            // Add the filename to the file containing the list of files to move to upper directory
                            calFilesTracker << errFileName.str() << std::endl;
                            // Close the file
                            errFile.close();
                        }
                        else { // There is a user supplied error covariance file
                            // Process the user supplied error covariance file
                            // Get the dimensions of the contents of this file
                            std::ifstream errFileUser(errFileToProcess);
                            int nrow = 0;
                            int ncol = 0;
                            std::string fileLine;

                            // Get the first line
                            getline(errFileUser, fileLine);
                            while (fileLine.empty()) {
                                getline(errFileUser, fileLine);
                            }
//                            // Check if there were any commas
//                            bool commaSeparated = false;
//                            if (fileLine.find(',') != std::string::npos) {
//                                commaSeparated = true;
//                            }
                            // Get the number of columns of the first row
                            char *entry;
                            entry = strtok(const_cast<char *>(fileLine.c_str()), " \t,");
                            while (entry != nullptr) { // while end of cstring is not reached
                                ++ncol;
                                entry = strtok(nullptr, " \t,");
                            }
                            // Create temporary file to hold the space separated error data. This file will be moved to the
                            // upper directory, and then the extension '.tmpFile' will be removed from the filename
                            std::string tmpErrorFileName = errFileToProcess + ".tmpFile";
                            std::ofstream tmpErrorFile(tmpErrorFileName);

                            // Now, loop over each line of the user supplied error covariance file
                            errFileUser.close();
                            errFileUser.open(errFileToProcess);
                            while (getline(errFileUser, fileLine)) {
                                if (!fileLine.empty()) {
                                    nrow++;
                                    // Get the number of columns of each row
                                    int numCols = 0;
                                    char *word;
                                    word = strtok(const_cast<char *>(fileLine.c_str()), " \t,");
                                    while (word != nullptr) { // while end of cstring is not reached
                                        ++numCols;
                                        tmpErrorFile << word << " ";
//                                        if (commaSeparated) {
//                                            tmpErrorFile << word << " ";
//                                        }
                                        word = strtok(nullptr, " \t,");
                                    }
                                    if (numCols != ncol) {
                                        std::cout << "ERROR: The number of columns must be the same for each row in the "
                                                     "error covariance file " << errFileToProcess << ". \nThe expected"
                                                  << " length is " << ncol << ", but the length of row " << nrow
                                                  << " is " << numCols << "." << std::endl;
                                        return EXIT_FAILURE;
                                    }
                                }
                            }
                            errFileUser.close();
                            tmpErrorFile.close();

                            if (nrow == 1) {
                                if (ncol == 1) {
                                    errType << "'scalar' ";
                                } else if (ncol == lengthList[responseNum]) {
                                    errType << "'diagonal' ";
                                } else {
                                    std::cout << "ERROR: The number of columns does not match the expected number of error "
                                                 "covariance terms. Expected " << lengthList[responseNum] << "terms but "
                                              << "got " << ncol << " terms." << std::endl;
                                    return EXIT_FAILURE;
                                }
                            } else if (nrow == lengthList[responseNum]) {
                                if (ncol == 1) {
                                    errType << "'diagonal' ";
                                } else if (ncol == lengthList[responseNum]) {
                                    errType << "'matrix' ";
                                } else {
                                    std::cout << "ERROR: The number of columns does not match the expected number of error "
                                                 "covariance terms. Expected " << lengthList[responseNum] << "terms but "
                                              << "got " << ncol << " terms." << std::endl;
                                    return EXIT_FAILURE;
                                }
                            } else {
                                std::cout << "ERROR: The number of rows does not match the expected number of error "
                                             "covariance terms. Expected " << lengthList[responseNum] << "terms but "
                                          << "got " << nrow << " terms." << std::endl;
                                return EXIT_FAILURE;
                            }
                            // Add this filename to the list of files to be moved
                            calFilesTracker << tmpErrorFileName << std::endl;
                        }
                        // =============================================
                    }
                }
            }
        }
    }
    // =============================================
    // When there are only scalar response terms
    // =============================================
    else {
        // Create an ofstream to write the data and error variances
        std::ofstream scalarCalDataFile;
        std::string scalarCalDataFileName = "quoFEMScalarCalibrationData.cal";
        // Add the name of this file that contains the calibration data and error variance values
        calFilesTracker << scalarCalDataFileName << std::endl;

        if (idResponse.compare("BayesCalibration") != 0) {
            // This is the case of deterministic calibration
            // A single calibration data file needs to be created, which contains the data
            // Renaming the spaced data file will suffice for this case
            std::rename(spacedFileName.c_str(), scalarCalDataFileName.c_str());
        }
        else {
            // This is the Bayesian calibration case.
            // A single calibration data file needs to be created, which contains the data and the variances
            scalarCalDataFile.open(scalarCalDataFileName.c_str(), std::fstream::out);
            spacedDataFile.open(spacedFileName.c_str(), std::fstream::in);
            // Loop over the number of experiments to write data to file line by line
            for (int expNum = 1; expNum <= numExperiments; expNum++) {
                // Get the calibration data
                getline(spacedDataFile, line);
                // Write this data to the scalar data file
                scalarCalDataFile << line;

                // For each response quantity, check if there is an error variance file
                for (int responseNum = 0; responseNum < numResponses; responseNum++) {
                    // Create filename for error variance
                    std::stringstream errFileName;
                    errFileName << edpList[responseNum] << "." << lineNum << ".sigma";
                    // Check if an error variance file with the created name is in the list of error files
                    std::string errFileToProcess;
                    if (readErrorFile) {// If any user supplied error variance files exist
                        for (const auto &path : errFileList) {
                            std::string base_filename = path.substr(path.find_last_of("/\\") + 1);
//                            std::cout << "Base filename: " << base_filename << std::endl;
                            if (base_filename == errFileName.str()) {
                                errFileToProcess = path;
                                break;
                            }
                        }
                        std::ifstream errFileUser(errFileToProcess);
                        std::string fileLine;
                        // Get the first line
                        getline(errFileUser, fileLine);
                        while (fileLine.empty()) {
                            getline(errFileUser, fileLine);
                        }
                        // Get the first word from the file
                        char *entry;
                        entry = strtok(const_cast<char *>(fileLine.c_str()), " \t,");
                        scalarCalDataFile << " " << entry;
                    }
                    else {// If user supplied error variance files do not exist
                        scalarCalDataFile << " " << "1";
                    }
                }
                scalarCalDataFile << std::endl;
            }
            errType << "'scalar' ";
            scalarCalDataFile.close();
            spacedDataFile.close();
        }
    }
    calFilesTracker.close();
    return numExperiments;
}

int
writeResponse(std::ostream &dakotaFile, json_t *rootEDP,  std::string idResponse, bool numericalGradients, bool numericalHessians,
              std::vector<std::string> &edpList, const char *calFileName, std::vector<double> &scaleFactors) {
  int numResponses = 0;

  dakotaFile << "responses\n";

  if (!idResponse.empty() && (idResponse.compare("calibration") != 0 || idResponse.compare("BayesCalibration") != 0))
    dakotaFile << "  id_responses = '" << idResponse << "'\n";

  //
  // look in file for EngineeringDemandParameters
  // .. if there parse edp for each event
  //

  json_t *EDPs = json_object_get(rootEDP,"EngineeringDemandParameters");

  if (EDPs != NULL) {

    numResponses = json_integer_value(json_object_get(rootEDP,"total_number_edp"));
    dakotaFile << " response_functions = " << numResponses << "\n response_descriptors = ";

    // for each event write the edps
    int numEvents = json_array_size(EDPs);

    // loop over all events
    for (int i=0; i<numEvents; i++) {

      json_t *event = json_array_get(EDPs,i);
      json_t *eventEDPs = json_object_get(event,"responses");
      int numResponses = json_array_size(eventEDPs);

      // loop over all edp for the event
      for (int j=0; j<numResponses; j++) {

	json_t *eventEDP = json_array_get(eventEDPs,j);
	const char *eventType = json_string_value(json_object_get(eventEDP,"type"));
	bool known = false;
	std::string edpAcronym("");
	const char *floor = NULL;
	std::cerr << "writeResponse: type: " << eventType;
	// based on edp do something
	if (strcmp(eventType,"max_abs_acceleration") == 0) {
	  edpAcronym = "PFA";
	  floor = json_string_value(json_object_get(eventEDP,"floor"));
	  known = true;
	} else if	(strcmp(eventType,"max_drift") == 0) {
	  edpAcronym = "PID";
	  floor = json_string_value(json_object_get(eventEDP,"floor2"));
	  known = true;
	} else if	(strcmp(eventType,"residual_disp") == 0) {
	  edpAcronym = "RD";
	  floor = json_string_value(json_object_get(eventEDP,"floor"));
	  known = true;
	} else if (strcmp(eventType,"max_pressure") == 0) {
	  edpAcronym = "PSP";
	  floor = json_string_value(json_object_get(eventEDP,"floor2"));
	  known = true;
	} else if (strcmp(eventType,"max_rel_disp") == 0) {
	  edpAcronym = "PFD";
	  floor = json_string_value(json_object_get(eventEDP,"floor"));
	  known = true;
	} else if (strcmp(eventType,"peak_wind_gust_speed") == 0) {
	  edpAcronym = "PWS";
	  floor = json_string_value(json_object_get(eventEDP,"floor"));
	  known = true;
	} else {
	  dakotaFile << "'" << eventType << "' ";
	  std::string newEDP(eventType);
	  edpList.push_back(newEDP);
	}

	if (known == true) {
	  json_t *dofs = json_object_get(eventEDP,"dofs");
	  int numDOF = json_array_size(dofs);

	  // loop over all edp for the event
	  for (int k=0; k<numDOF; k++) {
	    int dof = json_integer_value(json_array_get(dofs,k));
	    dakotaFile << "'" << i+1 << "-" << edpAcronym << "-" << floor << "-" << dof << "' ";
	    std::string newEDP = std::string(std::to_string(i+1)) + std::string("-")
	      + edpAcronym
	      + std::string("-")
	      + std::string(floor) +
	      std::string("-") + std::string(std::to_string(dof));
	    edpList.push_back(newEDP);
	  }
	}
      }
    }
  } else {

    //
    // quoFEM .. just a list of straight EDP
    //

    numResponses = json_array_size(rootEDP);

    std::vector<int> lenList(numResponses, 1);

    int numFieldResponses = 0;
    int numScalarResponses = 0;

    if (!(idResponse.compare("calibration") == 0 || idResponse.compare("BayesCalibration") == 0))
      dakotaFile << " response_functions = " << numResponses << "\n response_descriptors = ";
    else
      dakotaFile << " calibration_terms = " << numResponses << "\n response_descriptors = ";

      for (int j=0; j<numResponses; j++) {
          json_t *theEDP_Item = json_array_get(rootEDP,j);
          const char *theEDP = json_string_value(json_object_get(theEDP_Item,"name"));
          dakotaFile << "'" << theEDP << "' ";
          std::string newEDP(theEDP);
          edpList.push_back(newEDP);

          if (json_object_get(theEDP_Item,"type")) {
              std::string varType = json_string_value(json_object_get(theEDP_Item,"type"));
              if (varType.compare("field") == 0) {
                  numFieldResponses++;
              }
              else {
              numScalarResponses++;
              }
          }
      }

      if (numFieldResponses > 0) {
          if (!(idResponse.compare("calibration") == 0 || idResponse.compare("BayesCalibration") == 0)) {
              if (numScalarResponses > 0) {
                  dakotaFile << "\n  scalar_responses = " << numScalarResponses;
              }
              dakotaFile << "\n  field_responses = " << numFieldResponses << "\n  lengths = ";
          }
          else {
              if (numScalarResponses > 0) {
                  dakotaFile << "\n  scalar_calibration_terms = " << numScalarResponses;
              }
              dakotaFile << "\n  field_calibration_terms = " << numFieldResponses << "\n   lengths = ";
          }
          for (int j = 0; j < numResponses; j++) {
              json_t *theEDP_Item = json_array_get(rootEDP, j);
              std::string varType = json_string_value(json_object_get(theEDP_Item, "type"));
              if (varType.compare("field") == 0) {
                  int len = json_integer_value(json_object_get(theEDP_Item, "length"));
                  dakotaFile << len << " ";
                  lenList[j] = len;
              }
          }

//          bool readFieldCoords = true;
//          if (readFieldCoords) {
//              dakotaFile << "\n  read_field_coordinates" << "\n  num_coordinates_per_field = ";
//              for (int j = 0; j < numResponses; j++) {
//                  json_t *theEDP_Item = json_array_get(rootEDP, j);
//                  int numCoords = json_integer_value(json_object_get(theEDP_Item, "numIndCoords"));
//                  dakotaFile << numCoords << " ";
//              }
//          }
//
//      }
    }
        if ((idResponse.compare("calibration") == 0) || (idResponse.compare("BayesCalibration") == 0)) {
            std::vector<std::string> errFilenameList = {};
            std::stringstream errTypeStringStream;

            int numExp = processDataFiles(calFileName, edpList, lenList, numResponses, numFieldResponses, errFilenameList,
                                          errTypeStringStream, idResponse, scaleFactors);

            bool readCalibrationData = true;
            if (readCalibrationData) {
                if (numFieldResponses > 0) {
                    int nExp = numExp;
                    if (nExp < 1) {
                        nExp = 1;
                    }
                    dakotaFile << "\n  calibration_data";
                    dakotaFile << "\n   num_experiments = " << nExp;
                    if (idResponse.compare("BayesCalibration") == 0) {
                        dakotaFile << "\n   experiment_variance_type = ";
                        dakotaFile << errTypeStringStream.str();
                    }
                }
                else {
                    int nExp = numExp;
                    if (nExp < 1) {
                        nExp = 1;
                    }
                    dakotaFile << "\n  calibration_data_file = 'quoFEMScalarCalibrationData.cal'";
                    dakotaFile << "\n    freeform";
                    dakotaFile << "\n    num_experiments = " << nExp;
                    if (idResponse.compare("BayesCalibration") == 0) {
                        dakotaFile << "\n    experiment_variance_type = ";
                        dakotaFile << errTypeStringStream.str();
                    }
                }
            }
        }
    }


  if (numericalGradients == true)
    dakotaFile << "\n numerical_gradients";
  else
    dakotaFile << "\n no_gradients";

  if (numericalHessians == true)
    dakotaFile << "\n numerical_hessians\n\n";
  else
    dakotaFile << "\n no_hessians\n\n";

  return numResponses;
}


int
writeDakotaInputFile(std::ostream &dakotaFile,
		     json_t *uqData,
		     json_t *rootEDP,
		     struct randomVariables &theRandomVariables,
		     std::string &workflowDriver,
		     std::vector<std::string> &rvList,
		     std::vector<std::string> &edpList,
		     int evalConcurrency) {


  int evaluationConcurrency = evalConcurrency;

  // test if parallelExe is false, if so set evalConcurrency = 1;
  json_t *parallelExe = json_object_get(uqData, "parallelExecution");
  if (parallelExe != NULL) {
    if (json_is_false(parallelExe))
      evaluationConcurrency = 1;
  }

  const char *type = json_string_value(json_object_get(uqData, "uqType"));

  bool sensitivityAnalysis = false;
  if (strcmp(type, "Sensitivity Analysis") == 0)
    sensitivityAnalysis = true;

  json_t *EDPs = json_object_get(rootEDP,"EngineeringDemandParameters");
  int numResponses = 0;
  if (EDPs != NULL) {
    numResponses = json_integer_value(json_object_get(rootEDP,"total_number_edp"));
  } else {
    numResponses = json_array_size(rootEDP);
  }

  //
  // based on method do stuff
  //

  if ((strcmp(type, "Forward Propagation") == 0) || sensitivityAnalysis == true) {

    json_t *samplingMethodData = json_object_get(uqData,"samplingMethodData");

    const char *method = json_string_value(json_object_get(samplingMethodData,"method"));

    if (strcmp(method,"Monte Carlo")==0) {
      int numSamples = json_integer_value(json_object_get(samplingMethodData,"samples"));
      int seed = json_integer_value(json_object_get(samplingMethodData,"seed"));

      dakotaFile << "environment \n tabular_data \n tabular_data_file = 'dakotaTab.out' \n\n";
      dakotaFile << "method, \n sampling \n sample_type = random \n samples = " << numSamples << " \n seed = " << seed << "\n\n";

      if (sensitivityAnalysis == true)
	dakotaFile << "variance_based_decomp \n\n";

      const char * calFileName = new char[1];
      std::string emptyString;
      std::vector<double> scaleFactors;
      writeRV(dakotaFile, theRandomVariables, emptyString, rvList, true);
      writeInterface(dakotaFile, uqData, workflowDriver, emptyString, evaluationConcurrency);
      writeResponse(dakotaFile, rootEDP, emptyString, false, false, edpList, calFileName, scaleFactors);
    }

    else if (strcmp(method,"LHS")==0) {

      int numSamples = json_integer_value(json_object_get(samplingMethodData,"samples"));
      int seed = json_integer_value(json_object_get(samplingMethodData,"seed"));

      std::cerr << numSamples << " " << seed;

      dakotaFile << "environment \n tabular_data \n tabular_data_file = 'dakotaTab.out' \n\n";
      dakotaFile << "method,\n sampling\n sample_type = lhs \n samples = " << numSamples << " \n seed = " << seed << "\n\n";

      if (sensitivityAnalysis == true)
	  dakotaFile << "variance_based_decomp \n\n";


      const char * calFileName = new char[1];
      std::string emptyString;
      std::vector<double> scaleFactors;
      writeRV(dakotaFile, theRandomVariables, emptyString, rvList);
      writeInterface(dakotaFile, uqData, workflowDriver, emptyString, evaluationConcurrency);

      writeResponse(dakotaFile, rootEDP, emptyString, false, false, edpList, calFileName, scaleFactors);
    }

    /*
    else if (strcmp(method,"Importance Sampling")==0) {

      const char *isMethod = json_string_value(json_object_get(samplingMethodData,"ismethod"));
      int numSamples = json_integer_value(json_object_get(samplingMethodData,"samples"));
      int seed = json_integer_value(json_object_get(samplingMethodData,"seed"));

      dakotaFile << "environment \n tabular_data \n tabular_data_file = 'dakotaTab.out' \n\n";
      dakotaFile << "method, \n importance_sampling \n " << isMethod << " \n samples = " << numSamples << "\n seed = " << seed << "\n\n";
      const char *calFileName;
      std::string emptyString;
      writeRV(dakotaFile, theRandomVariables, emptyString, rvList);
      writeInterface(dakotaFile, uqData, workflowDriver, emptyString, evaluationConcurrency);
      writeResponse(dakotaFile, rootEDP, emptyString, false, false, edpList, calFileName);
    }
    */
//    }
  else if (strcmp(method,"Gaussian Process Regression")==0) {

      int trainingSamples = json_integer_value(json_object_get(samplingMethodData,"trainingSamples"));
      int trainingSeed = json_integer_value(json_object_get(samplingMethodData,"trainingSeed"));
      const char *trainMethod = json_string_value(json_object_get(samplingMethodData,"trainingMethod"));
      int samplingSamples = json_integer_value(json_object_get(samplingMethodData,"samplingSamples"));
      int samplingSeed = json_integer_value(json_object_get(samplingMethodData,"samplingSeed"));
      const char *sampleMethod = json_string_value(json_object_get(samplingMethodData,"samplingMethod"));

      const char *surrogateMethod = json_string_value(json_object_get(samplingMethodData,"surrogateSurfaceMethod"));

      std::string trainingMethod(trainMethod);
      std::string samplingMethod(sampleMethod);
      if (strcmp(trainMethod,"Monte Carlo") == 0)
	trainingMethod = "random";
      if (strcmp(sampleMethod,"Monte Carlo") == 0)
	samplingMethod = "random";


      dakotaFile << "environment \n method_pointer = 'SurrogateMethod' \n tabular_data \n tabular_data_file = 'dakotaTab.out'\n";
      dakotaFile << "custom_annotated header eval_id \n\n";

      dakotaFile << "method \n id_method = 'SurrogateMethod' \n model_pointer = 'SurrogateModel'\n";
      dakotaFile << " sampling \n samples = " << samplingSamples << "\n seed = " << samplingSeed << "\n sample_type = "
		 << samplingMethod << "\n\n";

      dakotaFile << "model \n id_model = 'SurrogateModel' \n surrogate global \n dace_method_pointer = 'TrainingMethod'\n "
		 << surrogateMethod << "\n\n";

      dakotaFile << "method \n id_method = 'TrainingMethod' \n model_pointer = 'TrainingModel'\n";
      dakotaFile << " sampling \n samples = " << trainingSamples << "\n seed = " << trainingSeed << "\n sample_type = "
		 << trainingMethod << "\n\n";

      dakotaFile << "model \n id_model = 'TrainingModel' \n single \n interface_pointer = 'SimulationInterface'";
      const char * calFileName = new char[1];
      std::string emptyString;
      std::vector<double> scaleFactors;
      std::string interfaceString("SimulationInterface");
      writeRV(dakotaFile, theRandomVariables, emptyString, rvList);
      writeInterface(dakotaFile, uqData, workflowDriver, interfaceString, evaluationConcurrency);
      writeResponse(dakotaFile, rootEDP, emptyString, false, false, edpList, calFileName, scaleFactors);

    }

    else if (strcmp(method,"Polynomial Chaos Expansion")==0) {

      const char *dataMethod = json_string_value(json_object_get(samplingMethodData,"dataMethod"));
      int intValue = json_integer_value(json_object_get(samplingMethodData,"level"));
      int samplingSeed = json_integer_value(json_object_get(samplingMethodData,"samplingSeed"));
      int samplingSamples = json_integer_value(json_object_get(samplingMethodData,"samplingSamples"));
      const char *sampleMethod = json_string_value(json_object_get(samplingMethodData,"samplingMethod"));

      std::string pceMethod;
      if (strcmp(dataMethod,"Quadrature") == 0)
	pceMethod = "quadrature_order = ";
      else if (strcmp(dataMethod,"Smolyak Sparse_Grid") == 0)
	pceMethod = "sparse_grid_level = ";
      else if (strcmp(dataMethod,"Stroud Cubature") == 0)
	pceMethod = "cubature_integrand = ";
      else if (strcmp(dataMethod,"Orthogonal Least_Interpolation") == 0)
	pceMethod = "orthogonal_least_squares collocation_points = ";
      else
	pceMethod = "quadrature_order = ";

      std::string samplingMethod(sampleMethod);
      if (strcmp(sampleMethod,"Monte Carlo") == 0)
	samplingMethod = "random";

      dakotaFile << "environment \n  tabular_data \n tabular_data_file = 'a.out'\n\n"; // a.out for trial data
      const char * calFileName = new char[1];
      std::string emptyString;
      std::vector<double> scaleFactors;
      std::string interfaceString("SimulationInterface");
      writeRV(dakotaFile, theRandomVariables, emptyString, rvList);
      writeInterface(dakotaFile, uqData, workflowDriver, interfaceString, evaluationConcurrency);
      int numResponse = writeResponse(dakotaFile, rootEDP, emptyString, false, false, edpList, calFileName, scaleFactors);

      dakotaFile << "method \n polynomial_chaos \n " << pceMethod << intValue;
      dakotaFile << "\n samples_on_emulator = " << samplingSamples << "\n seed = " << samplingSeed << "\n sample_type = "
		 << samplingMethod << "\n";
      dakotaFile << " probability_levels = ";
      for (int i=0; i<numResponse; i++)
	dakotaFile << " .1 .5 .9 ";
      dakotaFile << "\n export_approx_points_file = 'dakotaTab.out'\n\n"; // dakotaTab.out for surrogate evaluations
    }

  }

  else if ((strcmp(type, "Reliability Analysis") == 0)) {

    json_t *reliabilityMethodData = json_object_get(uqData,"reliabilityMethodData");

    const char *method = json_string_value(json_object_get(reliabilityMethodData,"method"));

    if (strcmp(method,"Local Reliability")==0) {

      const char *localMethod = json_string_value(json_object_get(reliabilityMethodData,"localMethod"));
      const char *mppMethod = json_string_value(json_object_get(reliabilityMethodData,"mpp_Method"));
      const char *levelType = json_string_value(json_object_get(reliabilityMethodData,"levelType"));
      const char *integrationMethod = json_string_value(json_object_get(reliabilityMethodData,"integrationMethod"));

      std::string intMethod;
      if (strcmp(integrationMethod,"First Order") == 0)
	intMethod = "first_order";
      else
	intMethod = "second_order";

      dakotaFile << "environment \n tabular_data \n tabular_data_file = 'dakotaTab.out' \n\n";
      if (strcmp(localMethod,"Mean Value") == 0) {
	dakotaFile << "method, \n local_reliability \n";
      } else {
	dakotaFile << "method, \n local_reliability \n mpp_search " << mppMethod
		   << " \n integration " << intMethod << " \n";
      }

      json_t *levels =  json_object_get(reliabilityMethodData, "probabilityLevel");
      if (levels == NULL) {
	return 0;
      }

      int numLevels = json_array_size(levels);
      if (strcmp(levelType, "Probability Levels") == 0)
	dakotaFile << " \n num_probability_levels = ";
      else
	dakotaFile << " \n num_response_levels = ";

      for (int i=0; i<numResponses; i++)
	dakotaFile << numLevels << " ";

      if (strcmp(levelType, "Probability Levels") == 0)
	dakotaFile << " \n probability_levels = " ;
      else
	dakotaFile << " \n response_levels = " ;

      for (int j=0; j<numResponses; j++) {
	for (int i=0; i<numLevels; i++) {
	    json_t *responseLevel = json_array_get(levels,i);
	    double val = json_number_value(responseLevel);
	    dakotaFile << val << " ";
	  }
	dakotaFile << "\n\t";
      }
      dakotaFile << "\n\n";
      const char * calFileName = new char[1];
      std::string emptyString;
      std::vector<double> scaleFactors;
      writeRV(dakotaFile, theRandomVariables, emptyString, rvList);
      writeInterface(dakotaFile, uqData, workflowDriver, emptyString, evaluationConcurrency);
      writeResponse(dakotaFile, rootEDP, emptyString, true, true, edpList, calFileName, scaleFactors);
    }

    else if (strcmp(method,"Global Reliability")==0) {

      const char *gp = json_string_value(json_object_get(reliabilityMethodData,"gpApproximation"));
      std::string gpMethod;
      if (strcmp(gp,"x-space") == 0)
	gpMethod = "x_gaussian_process";
      else
	gpMethod = "u_gaussian_process";


      json_t *levels =  json_object_get(reliabilityMethodData, "responseLevel");
      if (levels == NULL) {
	return 0;
      }
      int numLevels = json_array_size(levels);

      dakotaFile << "environment \n tabular_data \n tabular_data_file = 'dakotaTab.out' \n\n";
      dakotaFile << "method, \n global_reliability " << gpMethod << " \n"; // seed " << seed;

      dakotaFile << " \n num_response_levels = ";
      for (int i=0; i<numResponses; i++)
	dakotaFile << numLevels << " ";

      dakotaFile << " \n response_levels = " ;
      for (int j=0; j<numResponses; j++) {
	for (int i=0; i<numLevels; i++) {
	  json_t *responseLevel = json_array_get(levels,i);
	  double val = json_number_value(responseLevel);
	  dakotaFile << val << " ";
	}
	dakotaFile << "\n\t";
      }
      dakotaFile << "\n\n";
      const char * calFileName = new char[1];
      std::string emptyString;
      std::vector<double> scaleFactors;
      writeRV(dakotaFile, theRandomVariables, emptyString, rvList);
      writeInterface(dakotaFile, uqData, workflowDriver, emptyString, evaluationConcurrency);
      writeResponse(dakotaFile, rootEDP, emptyString, true, false, edpList, calFileName, scaleFactors);
    }

    else if (strcmp(method,"Importance Sampling")==0) {

      const char *isMethod = json_string_value(json_object_get(reliabilityMethodData,"ismethod"));
      int numSamples = json_integer_value(json_object_get(reliabilityMethodData,"samples"));
      int seed = json_integer_value(json_object_get(reliabilityMethodData,"seed"));

      json_t *levels =  json_object_get(reliabilityMethodData, "responseLevel");
      if (levels == NULL) {
        return 0;
      }

      int numLevels = json_array_size(levels);

       dakotaFile << "environment \n tabular_data \n tabular_data_file = 'dakotaTab.out' \n\n";
       dakotaFile << "method, \n importance_sampling \n " << isMethod << " \n samples = " << numSamples << "\n seed = " << seed << "\n\n";

    //   std::string emptyString;
    //   writeRV(dakotaFile, theRandomVariables, emptyString, rvList);
    //   writeInterface(dakotaFile, uqData, workflowDriver, emptyString, evaluationConcurrency);
    //   writeResponse(dakotaFile, rootEDP, emptyString, false, false, edpList);
      dakotaFile << " \n num_response_levels = ";
      for (int i=0; i<numResponses; i++)
        dakotaFile << numLevels << " ";

      dakotaFile << " \n response_levels = " ;
      for (int j=0; j<numResponses; j++) {
        for (int i=0; i<numLevels; i++) {
          json_t *responseLevel = json_array_get(levels,i);
          double val = json_number_value(responseLevel);
          dakotaFile << val << " ";
        }
        dakotaFile << "\n\t";
      }
      dakotaFile << "\n\n";

      const char * calFileName = new char[1];;
      std::string emptyString;
      std::vector<double> scaleFactors;
      writeRV(dakotaFile, theRandomVariables, emptyString, rvList);
      writeInterface(dakotaFile, uqData, workflowDriver, emptyString, evaluationConcurrency);
      writeResponse(dakotaFile, rootEDP, emptyString, true, false, edpList, calFileName, scaleFactors);
    }

  } else if ((strcmp(type, "Parameters Estimation") == 0)) {

    json_t *methodData = json_object_get(uqData,"calibrationMethodData");

    const char *method = json_string_value(json_object_get(methodData,"method"));

    std::string methodString("nl2sol");
    if (strcmp(method,"OPT++GaussNewton")==0)
      methodString = "optpp_g_newton";

    int maxIterations = json_integer_value(json_object_get(methodData,"maxIterations"));
    double tol = json_number_value(json_object_get(methodData,"convergenceTol"));
//    const char *factors = json_string_value(json_object_get(methodData,"factors"));
    const char *calFileName = json_string_value(json_object_get(methodData, "calibrationDataFile"));

    dakotaFile << "environment \n tabular_data \n tabular_data_file = 'dakotaTab.out' \n\n";

    dakotaFile << "method, \n " << methodString << "\n  convergence_tolerance = " << tol
	       << " \n   max_iterations = " << maxIterations;

//    if (strcmp(factors,"") != 0)
    dakotaFile << "\n  scaling\n";

    dakotaFile << "\n\n";

    std::string calibrationString("calibration");
    std::string emptyString;
    std::vector<double> scaleFactors;
    writeRV(dakotaFile, theRandomVariables, emptyString, rvList);
    writeInterface(dakotaFile, uqData, workflowDriver, emptyString, evaluationConcurrency);
    writeResponse(dakotaFile, rootEDP, calibrationString, true, false, edpList, calFileName, scaleFactors);

//    dakotaFile << "\n  primary_scales = 1052.69 1.53\n";
//    if (strcmp(factors,"") != 0) {
//      dakotaFile << "\n  primary_scale_types = \"value\" \n  primary_scales = ";
//      std::string factorString(factors);
//      std::stringstream factors_stream(factorString);
//      std::string tmp;
//      while (factors_stream >> tmp) {
//	// maybe some checks, i.e. ,
//	dakotaFile << tmp << " ";
//      }
//      dakotaFile << "\n";
//    }

  } else if ((strcmp(type, "Inverse Problem") == 0)) {

    json_t *methodData = json_object_get(uqData,"bayesianCalibrationMethodData");

    const char *method = json_string_value(json_object_get(methodData,"method"));

    /*
    const char *emulator = json_string_value(json_object_get(methodData,"emulator"));
    std::string emulatorString("gaussian_process");
    if (strcmp(emulator,"Polynomial Chaos")==0)
      emulatorString = "pce";
    else if (strcmp(emulator,"Multilevel Polynomial Chaos")==0)
      emulatorString = "ml_pce";
    else if (strcmp(emulator,"Multifidelity Polynomial Chaos")==0)
      emulatorString = "mf_pce";
    else if (strcmp(emulator,"Stochastic Collocation")==0)
      emulatorString = "sc";
    */

    int chainSamples = json_integer_value(json_object_get(methodData,"chainSamples"));
    int seed = json_integer_value(json_object_get(methodData,"seed"));
    int burnInSamples = json_integer_value(json_object_get(methodData,"burnInSamples"));
    int jumpStep = json_integer_value(json_object_get(methodData,"jumpStep"));
    //    int maxIterations = json_integer_value(json_object_get(methodData,"maxIter"));
    //    double tol = json_number_value(json_object_get(methodData,"tol"));
    const char *calFileName = json_string_value(json_object_get(methodData, "calibrationDataFile"));

      if (strcmp(method,"DREAM")==0) {

      int chains = json_integer_value(json_object_get(methodData,"chains"));

      dakotaFile << "environment \n tabular_data \n tabular_data_file = 'dakotaTab.out' \n\n";
      dakotaFile << "method \n bayes_calibration dream "
		 << "\n  chain_samples = " << chainSamples
		 << "\n  chains = " << chains
		 << "\n  jump_step = " << jumpStep
		 << "\n  burn_in_samples = " << burnInSamples
		 << "\n  calibrate_error_multipliers per_response";

	  dakotaFile << "\n  scaling\n" << "\n";

    } else {

      const char *mcmc = json_string_value(json_object_get(methodData,"mcmcMethod"));
      std::string mcmcString("dram");
      if (strcmp(mcmc,"Delayed Rejection")==0)
	mcmcString = "delayed_rejection";
      else if (strcmp(mcmc,"Adaptive Metropolis")==0)
	mcmcString = "adaptive_metropolis";
      else if (strcmp(mcmc,"Metropolis Hastings")==0)
	mcmcString = "metropolis_hastings";
      else if (strcmp(mcmc,"Multilevel")==0)
	mcmcString = "multilevel";

      dakotaFile << "environment \n tabular_data \n tabular_data_file = 'dakotaTab.out' \n\n";
      dakotaFile << "method \n bayes_calibration queso\n  " << mcmc
		 << "\n  chain_samples = " << chainSamples
		 << "\n  burn_in_samples = " << burnInSamples << "\n\n";
    }

    std::string calibrationString("BayesCalibration");
    std::string emptyString;
    std::vector<double> scaleFactors;
    writeRV(dakotaFile, theRandomVariables, emptyString, rvList, false);
    writeInterface(dakotaFile, uqData, workflowDriver, emptyString, evaluationConcurrency);
    writeResponse(dakotaFile, rootEDP, calibrationString, false, false, edpList, calFileName, scaleFactors);
//    calDataFile.close();

  } else {
    std::cerr << "uqType: NOT KNOWN\n";
    return -1;
  }
  return 0;
}


