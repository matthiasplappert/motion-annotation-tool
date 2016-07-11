#include <Glacier2/Session.ice>

module MotionDatabase {
	exception InternalErrorException {
		string errorMessage;
	};
	
	exception InvalidParameterException {
		string parameterName;
	};
	
	exception NotAuthorizedException {};
	exception TooManyOpenFilesException {};
	
	class Institution;
	class MotionDescriptionTreeNode;
	class File;
	class Motion;
	class Project;
	class Subject;
	class MoCapObject;
	
	sequence<byte> ByteSequence;
	sequence<long> LongSequence;
	sequence<string> StringSequence;
	sequence<Institution> InstitutionList;
	sequence<MotionDescriptionTreeNode> MotionDescriptionTreeNodeList;
	sequence<File> FileList;
	sequence<Motion> MotionList;
	sequence<Project> ProjectList;
	sequence<Subject> SubjectList;
	sequence<MoCapObject> MoCapObjectList;
	
	dictionary<string, short> StringShortDictionary;

	enum VisibilityLevel { Public, Protected, Internal };
	
	class Institution {
		long id;
		string acronym;
		string name;
	};
	
	class MotionDescriptionTreeNode {
		long id;
		string label;
		MotionDescriptionTreeNodeList children;
	};
	
	class DatabaseObject {
		long id;
		long createdDate;
		string createdUser;
		long modifiedDate;
		string modifiedUser;
		StringSequence writeGroups;
		StringSequence readProtectedGroups;
		StringShortDictionary fileTypeCounts;
	};
	
	class File {
		long id;
		long createdDate;
		string createdUser;
		string fileName;
		string fileType;
		long attachedToId;
		string description;
		VisibilityLevel visibility;
		File originatedFrom;
	};
	
	class Motion extends DatabaseObject {
		Institution associatedInstitution;
		MotionDescriptionTreeNodeList motionDescriptions;
		Project associatedProject;
		SubjectList associatedSubjects;
		MoCapObjectList associatedObjects;
		string date;
		string comment;
	};
	
	class Project extends DatabaseObject {
		string name;
		string comment;
	};
	
	class Subject extends DatabaseObject {
		string firstName;
		string lastName;
		string comment;
		byte gender;
		short age;
		short weight;
		short height;
		StringShortDictionary anthropometricsTable;
	};
	
	class MoCapObject extends DatabaseObject {
		string label;
		string comment;
		string modelSettingsJSON;
	};
	
	interface FileReader {
		void destroy();
		
		idempotent long getSize() throws InternalErrorException;
		ByteSequence readChunk(long length) throws InternalErrorException, InvalidParameterException;
		idempotent void seek(long pos) throws InternalErrorException, InvalidParameterException;
	};
	
	interface FileWriter {
		void destroy();
		
		void writeChunk(ByteSequence data) throws InternalErrorException;
	};
	
	interface MotionDatabaseSession extends Glacier2::Session {
		idempotent string pingServer(string echoString);
		
		idempotent InstitutionList listInstitutions() throws InternalErrorException;
		idempotent MotionDescriptionTreeNodeList getMotionDescriptionTree() throws InternalErrorException;
		
		idempotent Motion getMotion(long motionId) throws InternalErrorException, InvalidParameterException;
		idempotent long countMotions(LongSequence filterMotionDescription, LongSequence filterProject, LongSequence filterInstitution,
			LongSequence filterSubject, LongSequence filterObject, string motionDescriptionSearchTerm) throws InternalErrorException,
			InvalidParameterException;
		idempotent MotionList listMotions(LongSequence filterMotionDescription, LongSequence filterProject, LongSequence filterInstitution,
			LongSequence filterSubject, LongSequence filterObject, string motionDescriptionSearchTerm, string sortField, long limit,
			long offset) throws InternalErrorException, InvalidParameterException;
		idempotent ProjectList listProjects() throws InternalErrorException;
		idempotent SubjectList listSubjects() throws InternalErrorException;
		idempotent MoCapObjectList listObjects() throws InternalErrorException;
		
		idempotent File getFile(long fileId) throws InternalErrorException, InvalidParameterException;
		idempotent FileList listFiles(long databaseObjectId) throws InternalErrorException, InvalidParameterException;
		idempotent FileReader* getFileReader(long fileId) throws InternalErrorException, InvalidParameterException, NotAuthorizedException,
		    TooManyOpenFilesException;

		FileWriter* getFileWriter(long databaseObjectId, string fileName, string fileType, string description, VisibilityLevel visibility,
		    optional(1) long originatedFromId) throws InternalErrorException, InvalidParameterException, NotAuthorizedException,
		    TooManyOpenFilesException;
		void deleteFile(long fileId) throws InternalErrorException, InvalidParameterException, NotAuthorizedException;
	};
};